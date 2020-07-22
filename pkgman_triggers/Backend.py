from abc import ABC, abstractmethod

from . import Trigger


class Backend(ABC):
	__slots__ = ()

	@abstractmethod
	def checkTrigger(self, t: Trigger):
		raise NotImplementedError
