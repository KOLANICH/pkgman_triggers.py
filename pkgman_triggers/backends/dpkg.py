import os
from pprint import pprint
from warnings import warn

import bencodepy

from .. import TriggerManager
from ..events import Event
from ..PackageInfo import PackageInfo

benc = bencodepy.Bencode(encoding="utf-8", dict_ordered=True)


class DpkgInfo:
	ENV_VARS_REMAPPING = {
		"action": "DPKG_HOOK_ACTION",
		"configDir": "DPKG_ADMINDIR",
		"maintscriptPackageRefCount": "DPKG_MAINTSCRIPT_PACKAGE_REFCOUNT",
		"maintScriptName": "DPKG_MAINTSCRIPT_NAME",
		"maintScriptDebug": "DPKG_MAINTSCRIPT_DEBUG",
		"dpkgVersion": "DPKG_RUNNING_VERSION",
	}
	__slots__ = ("callType", "triggerers", "triggeree") + tuple(ENV_VARS_REMAPPING)

	def __init__(self, argv=()):
		if len(argv) > 1 and argv[0].endswith(".postinst"):
			self.callType = "maintainer_script"
		else:
			self.callType = "hook"

		if self.callType == "maintainer_script":
			action = argv[1]
			something = argv[2]

		self.triggeree = PackageInfo(os.environ.get("DPKG_MAINTSCRIPT_PACKAGE", None), os.environ.get("DPKG_MAINTSCRIPT_ARCH", None), None)
		triggerersBencoded = os.environ.get("DPKG_TRIGGERER_PACKAGES_INFO", None)
		if triggerersBencoded:
			triggerersBencDecode = benc.decode(triggerersBencoded)

			if isinstance(triggerersBencDecode, dict):
				self.triggerers = []
				for name, info in triggerersBencDecode.items():
					self.triggerers.append(PackageInfo(name, info.get("A", None), info.get("V", None)))
			else:
				self.triggerers = None
		else:
			self.triggerers = None

		for name, envName in self.__class__.ENV_VARS_REMAPPING.items():
			setattr(self, name, os.environ.get(envName, None))

	def toEvents(self):
		if self.triggerers:
			for triggerer in self.triggerers:
				yield Event(triggerer, self.triggeree, None)
		else:
			warn("The version of dpkg used (" + repr(self.dpkgVersion) + ") doesn't expose the info about triggerers.")  # pylint:disable=no-member
			yield Event(None, self.triggeree, None)

	def __repr__(self):
		return self.__class__.__name__ + "<" + ", ".join((k + "=" + repr(getattr(self, k))) for k in self.__class__.__slots__) + ">"


def process(argv):
	i = DpkgInfo(argv)
	pprint(i)

	with TriggerManager() as tm:
		tm.processEvents(i.toEvents())


if __name__ == "__main__":
	print("dpkg trigger called")
	process()
