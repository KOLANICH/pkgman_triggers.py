from abc import ABC, abstractmethod

from .events import Event
from .PackageInfo import PackageInfo


class Matcher(ABC):
	__slots__ = ()

	@abstractmethod
	def __call__(self, event: Event):
		raise NotImplementedError


class IPackageMatcher(Matcher):
	__slots__ = ()

	@abstractmethod
	def matchTriggerer(self, pkgInfo: PackageInfo):
		raise NotImplementedError

	def __call__(self, event: Event):
		if event.triggerer:
			print(event.triggerer)
			mr = self.matchTriggerer(event.triggerer)
			if mr:
				return mr
		return False


class PackageNameMatcher(IPackageMatcher):
	"""Matches changes in some package"""

	__slots__ = ("rx",)

	def __init__(self, rx):
		self.rx = rx

	def matchTriggerer(self, pkgInfo: PackageInfo):
		print(pkgInfo, self.rx)
		return self.rx.match(pkgInfo.name)
