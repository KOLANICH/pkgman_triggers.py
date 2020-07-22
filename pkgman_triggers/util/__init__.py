from collections.abc import Mapping, Sequence


def universalKeys(coll):
	if isinstance(coll, Mapping):
		return coll.keys()
	if isinstance(coll, Sequence):
		return range(len(coll))
	raise TypeError(type(coll))


def universalValues(coll):
	if isinstance(coll, Mapping):
		return coll.values()
	if isinstance(coll, Sequence):
		return coll
	raise TypeError(type(coll))


def universalItems(coll):
	if isinstance(coll, Mapping):
		return coll.items()
	if isinstance(coll, Sequence):
		return enumerate(coll)
	raise TypeError(type(coll))
