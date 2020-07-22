import typing
import warnings
from collections import OrderedDict
import pkg_resources
from pkg_resources import EntryPoint
import json
import re

from .PackageInfo import PackageInfo
from .triggers import Trigger, Module, TemporaryID
from .matchers import *
from .AuthDB import AuthDB


validNameRx = re.compile("^[a-zA-Z][\\w-]+$")

def findFirstFreeUnusedCellInUnknown(coll) -> int:
	i = 0
	while i in coll:
		i += 1
	return i


def recognizeBackends(ep: EntryPoint) -> Trigger:
	if hasattr(ep.__class__, "__slots__") and "metadata" in ep.__class__.__slots__:
		metadata = ep.metadata
	else:
		encoded = ep.name.split("@", 1)
		if len(encoded) > 1:
			try:
				metadata = json.loads(encoded[1])
				ep.name = encoded[0].strip()
			except json.JSONDecodeError:
				warnings.warn("Entry point " + repr(ep) + " is invalid. The value after @ must be must be a valid JSON!.")
				return None

	print("metadata", metadata)
	if metadata:
		if not validNameRx.match(ep.name):
			warnings.warn("Trigger name is invalid. Must match " + repr(validNameRx))

		paths = metadata.get("paths", ())
		named = metadata.get("named", {})
		packages = metadata.get("packages", {})
		if not paths and not named and not packages:
			warnings.warn("Entry point " + repr(ep) + " is invalid. Either paths or named or packages must be specified.")
			return None

		matchers = []

		if packages:
			for pkg in packages:
				if isinstance(pkg, str):
					matchers.append(PackageNameMatcher(re.compile(pkg)))
		else:
			warnings.warn("Other matchers are not yet implemented.")

		return Trigger(ep, matchers)

	warnings.warn("Entry point " + repr(ep) + " is invalid. JSON metadata must be present!.")
	return None


class TriggerManager:
	__slots__ = ("registeredModules", "unknownModules", "db")

	def __init__(self) -> None:
		self.db = AuthDB()
		self.registeredModules = None
		self.unknownModules = None

	def __enter__(self) -> "TriggerManager":
		self.db = self.db.__enter__()
		pts = pkg_resources.iter_entry_points(group="pkgman_triggers")
		triggers = sorted(filter(None, map(recognizeBackends, pts)), key=lambda t: (t.moduleName, t.path))
		print(triggers)
		modules = {}

		self.registeredModules = OrderedDict()
		self.unknownModules = {}

		for t in triggers:
			dId = id(t.entryPoint.dist)
			module = modules.get(dId, None)
			if module is None:
				module = modules[dId] = Module(t.entryPoint.dist)
				print("module.dist", module.dist)
				print("module.name", module.name)
				pkgInfo = self.db.findPackageByPath(t.path)

				if pkgInfo:
					print(dict(pkgInfo))
					module.id = pkgInfo["id"]
					module.status = pkgInfo["status"]
					self.registeredModules[module.id] = module
				else:
					module.id = TemporaryID(len(self.unknownModules))
					module.status = False
					self.unknownModules[module.id] = module

			t.module = module
			trigInfo = self.db.findTriggerByModuleAndName(module.id, t.internalName)
			if trigInfo:
				t.id = trigInfo["id"]
				t.status = trigInfo["status"]
				module.registeredTriggers[t.id] = t
			else:
				t.id = TemporaryID(len(module.unknownTriggers))
				t.status = False
				module.unknownTriggers[t.id] = t

		return self

	def setPackageEnabled(self, m: Module, status: typing.Optional[int]):
		self.db.setPackageEnabled(m.id, status)
		m.status = status

	def setTriggerEnabled(self, t: Trigger, status: typing.Optional[int]):
		self.db.setTriggerEnabled(t.id, status)
		t.status = status

	def registerPackage(self, idx):
		pkg = self.unknownModules[idx]
		registeredIdx = self.db.registerPackage(pkg.name, pkg.path)
		if isinstance(pkg.id, TemporaryID):
			pkg.id = registeredIdx
			assert registeredIdx not in self.registeredModules
			self.registeredModules[registeredIdx] = pkg
			del self.unknownModules[idx]
		else:
			assert pkg.id == registeredIdx
		return pkg

	def registerTrigger(self, package, idx):
		t = package.unknownTriggers[idx]
		registeredIdx = self.db.registerTrigger(package.id, t.internalName)
		print("registeredIdx", repr(registeredIdx))
		if isinstance(t.id, TemporaryID):
			t.id = registeredIdx
			print("t.id", repr(t.id))
			assert registeredIdx not in package.registeredTriggers
			package.registeredTriggers[registeredIdx] = t
			del package.unknownTriggers[idx]
		else:
			assert t.id == registeredIdx

	def unregisterTrigger(self, trigger):
		dbId = trigger.id
		del trigger.module.registeredTriggers[trigger.id]
		trigger.id = TemporaryID(findFirstFreeUnusedCellInUnknown(trigger.module.unknownTriggers))
		trigger.module.unknownTriggers[trigger.id] = trigger
		self.db.unregisterTriggerById(dbId)

	def unregisterPackage(self, package):
		dbId = package.id

		del self.registeredModules[package.id]
		package.id = TemporaryID(findFirstFreeUnusedCellInUnknown(self.unknownModules))
		self.unknownModules[package.id] = package

		#self.db.unregisterPackageTriggersByParentId(package.id)
		self.db.unregisterPackageById(dbId)

	def __exit__(self, *args, **kwargs) -> None:
		self.db.__exit__(*args, **kwargs)

	def processEvents(self, events):
		for evt in events:
			self.processEvent(evt)

	def processEvent(self, evt):
		for m in self.registeredModules:
			for t in m.registeredTriggers:
				if t.status:
					matchResults = t.match(evt)
					if matchResults:
						t(matchResults)
