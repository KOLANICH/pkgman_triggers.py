import typing
from collections import OrderedDict
from pathlib import Path

from pkg_resources import EggInfoDistribution, EntryPoint

from pkgman_triggers.matchers import PackageNameMatcher

moduleNameEpNameSeparator = "%"


class TemporaryID(int):
	__slots__ = ()


class Registrable:
	__slots__ = ("id", )

	@property
	def registered(self):
		return not isinstance(self.id, TemporaryID)

	def __init__(self, iD: int) -> None:
		self.id = iD

class Enableable(Registrable):
	__slots__ = ("status", )

	def __init__(self, iD: int, status: bool) -> None:
		super().__init__(iD)
		self.status = status

class Module(Enableable):
	__slots__ = ("id", "status", "registeredTriggers", "unknownTriggers", "dist", "path")

	def __init__(self, dist: EggInfoDistribution) -> None:
		super().__init__(None, None)
		self.registeredTriggers = OrderedDict()
		self.unknownTriggers = {}
		self.dist = dist
		self.path = Path(dist.module_path).absolute().resolve()

	@property
	def name(self) -> str:
		return self.dist.project_name

	@property
	def version(self):
		return self.dist.version


class Trigger(Enableable):
	__slots__ = ("id", "module", "status", "entryPoint", "matchers")

	@property
	def internalName(self) -> str:
		return self.entryPoint.name

	@property
	def moduleName(self) -> str:
		return self.entryPoint.module_name

	@property
	def path(self) -> Path:
		return Path(self.entryPoint.dist.module_path).absolute().resolve()

	@property
	def name(self) -> str:
		return moduleNameEpNameSeparator.join((self.moduleName, self.internalName))

	def __init__(self, entryPoint: EntryPoint, matchers: typing.Iterable[PackageNameMatcher]) -> None:
		super().__init__(None, None)
		self.module = None
		self.entryPoint = entryPoint
		self.matchers = matchers

	def match(self, evt):
		for m in self.matchers:
			matchRes = m(evt)
			print("matchRes", matchRes)
			if matchRes:
				return matchRes
		return None

	def __call__(self, matchResults):
		print("matched", self, matchResults)
		return self.entryPoint.resolve()(matchResults)

	def __repr__(self) -> str:
		return self.__class__.__name__ + "<" + ", ".join((repr(self.id), repr(self.name),)) + ">"
