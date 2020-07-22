from pathlib import Path

from plumbum import cli

from RichConsole import groups

from . import TriggerManager
from .backends import dpkg
from .triggers import moduleNameEpNameSeparator
from .util import universalItems, universalKeys, universalValues

backends = [dpkg]


class style:
	# pylint:disable=no-member
	green = groups.Fore.green
	red = groups.Fore.red
	disabledName = groups.CrossedOut.crossedOut

	internalName = groups.Fore.cyan
	moduleName = red
	ordinal = groups.Fore.yellow
	path = groups.Fore.magenta


class CLI(cli.Application):
	pass


statusMapping = {
	# pylint:disable=no-member
	True: style.green("ON✅"),
	False: style.red("OFF❌"),
}


def genCLIOnOff(status: int):
	return statusMapping[bool(status)]


def makeModuleRecordStrRepr(iD, m):
	modFancyName = style.moduleName(m.name)
	if not m.status:
		modFancyName = style.disabledName(modFancyName)
	return style.ordinal(iD) + "\t" + modFancyName + "\t" + style.path(m.path) + "\t" + genCLIOnOff(m.status)


def makeTriggerRecordStrRepr(iD, t):
	modFancyName = moduleNameEpNameSeparator + style.internalName(t.internalName)
	if not t.status:
		modFancyName = style.disabledName(modFancyName)
	return style.ordinal(iD) + "\t" + modFancyName + "\t" + genCLIOnOff(t.status)


unregisteredMarker = "@"


class ParsedId:
	__slots__ = ("collection", "idx")

	@property
	def pkg(self):
		return self.collection[self.idx]

	def __init__(self, idStr: str, tm):
		pkg = None

		if idStr[0] == unregisteredMarker:
			idStr = idStr[1:]
			self.collection = tm.unknownModules
		else:
			self.collection = tm.registeredModules

		try:
			iD = int(idStr)
			self.idx = iD
			return
		except ValueError:
			pass

		try:
			pathCand = Path(idStr).absolute().resolve()
		except ValueError:
			pathCand = None
		except PermissionError:
			pathCand = None

		for idx, pkg in universalItems(self.collection):
			print("pathCand", pathCand, pkg.path)
			if pkg.name == idStr or pkg.path == pathCand:
				self.idx = idx
				return
		raise KeyError(idStr)


def printTriggersSection(label, marker, section):
	if section:
		print("\t" + label + ":")
		for i, m in universalItems(section):
			print("\t" + makeTriggerRecordStrRepr(marker + str(i), m))


def printModuleTriggers(module):
	printTriggersSection("Registered", "", module.registeredTriggers)
	printTriggersSection("Unregistered", unregisteredMarker, module.unknownTriggers)


def printModulesSection(label, marker, section):
	if section:
		print(label + ":")
		for i, m in universalItems(section):
			print(makeModuleRecordStrRepr(marker + str(i), m))
			printModuleTriggers(m)


class ModuleCommandCLI(cli.Application):
	processAllTriggers = cli.Flag(["-A", "--all-triggers"], help="Also enable all triggers")


@CLI.subcommand("list")
class ListCLI(cli.Application):
	def main(self):  # pylint:disable=arguments-differ
		with TriggerManager() as tm:
			printModulesSection("Registered", "", tm.registeredModules)
			printModulesSection("Unregistered", unregisteredMarker, tm.unknownModules)


@CLI.subcommand("register")
class RegisterCLI(ModuleCommandCLI):
	@staticmethod
	def registerChildTriggers(tm, iD):
		print("iD.pkg.unknownTriggers", iD.pkg.unknownTriggers)
		for tId in tuple(universalKeys(iD.pkg.unknownTriggers)):
			tm.registerTrigger(iD.pkg, tId)

	def main(self, *ids):  # pylint:disable=arguments-differ
		print("ids", ids)
		with TriggerManager() as tm:
			for iD in ids:
				iD = ParsedId(iD, tm)
				pkg = iD.pkg
				if iD.collection is not tm.registeredModules:
					print("Registering", pkg)
					newIdx = tm.registerPackage(iD.idx).id
					iD.idx, iD.collection = newIdx, tm.registeredModules
					print("Registering all the triggers in", pkg)
					if self.processAllTriggers:
						self.registerChildTriggers(tm, iD)
				else:
					if not self.processAllTriggers:
						print("Unregistered packages ids are volatile and start from `#`. `" + str(iD) + "` was given")
					else:
						self.registerChildTriggers(tm, iD)


class PackageToggleCLI(ModuleCommandCLI):
	def toggle(self, desiredState, ids):
		with TriggerManager() as tm:
			for iD in ids:
				iD = ParsedId(iD, tm)
				tm.setPackageEnabled(iD.pkg, desiredState)
				if self.processAllTriggers:
					for t in tuple(universalValues(iD.pkg.registeredTriggers)):
						print("t", t)
						tm.setTriggerEnabled(t, desiredState)


@CLI.subcommand("enable")
class EnableCLI(PackageToggleCLI):
	def main(self, *ids):
		return self.toggle(True, ids)


@CLI.subcommand("disable")
class DisableCLI(PackageToggleCLI):
	def main(self, *ids):
		return self.toggle(False, ids)


@CLI.subcommand("clean")
class CleanCLI(ModuleCommandCLI):
	"""Removes the entities from the DB"""

	def main(self, *ids):
		with TriggerManager() as tm:
			for iD in ids:
				iD = ParsedId(iD, tm)
				tm.unregisterPackage(iD.pkg)


@CLI.subcommand("gui")
class GUI(cli.Application):
	"""A Qt 5 (PySide2)-based GUI"""

	def main(self):  # pylint:disable=arguments-differ
		from .gui import makeApp  # pylint:disable=import-outside-toplevel
		return makeApp()


if __name__ == "__main__":
	CLI.run()
