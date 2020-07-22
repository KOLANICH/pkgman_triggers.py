class Event:
	__slots__ = ("triggerer", "triggeree", "pathsAffected")

	def __init__(self, triggerer, triggeree, pathsAffected):
		self.triggerer = triggerer
		self.triggeree = triggeree
		self.pathsAffected = pathsAffected
