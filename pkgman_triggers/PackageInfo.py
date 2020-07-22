class PackageInfo:
	__slots__ = ("name", "version", "arch")

	def __init__(self, name: str, version: str, arch: str):
		self.name = name
		self.arch = arch
		self.version = version

	def __repr__(self):
		return self.__class__.__name__ + "(" + ", ".join(repr(getattr(self, k)) for k in self.__class__.__slots__) + ")"
