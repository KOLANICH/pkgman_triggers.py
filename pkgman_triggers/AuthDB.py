import typing
import sqlite3
from collections import OrderedDict
from pathlib import Path

from .defaults import configPath

DB_SCHEMA = OrderedDict(
	(
		(
			"packages",
			"""
				`id` INTEGER NOT NULL PRIMARY KEY,
				`name` TEXT NOT NULL UNIQUE,
				`path` TEXT NOT NULL UNIQUE,
				`status` INTEGER DEFAULT 0 NOT NULL
			""",
		),
		(
			"triggers",
			"""
				`id` INTEGER NOT NULL PRIMARY KEY,
				`package` INTEGER NOT NULL,
				`name` TEXT NOT NULL,
				`status` INTEGER DEFAULT 0 NOT NULL,
				`managers` INTEGER DEFAULT 0 NOT NULL,
				UNIQUE(package, name)
				FOREIGN KEY(`package`) REFERENCES `packages`(`id`)
			""",
		),
		(
			"conditions",
			"""
				`trigger` INTEGER NOT NULL,
				`hash` BLOB NOT NULL,
				`type` INTEGER NOT NULL ,
				`status` INTEGER DEFAULT 0 NOT NULL,
				PRIMARY KEY(trigger, hash)
				FOREIGN KEY(`trigger`) REFERENCES `triggers`(`id`)
			""",
		),
	)
)


class AuthDB:
	__slots__ = ("db", "dbPath")

	def __init__(self, dbPath: typing.Optional[Path] = None) -> None:
		if dbPath is None:
			dbPath = configPath

		self.dbPath = dbPath
		self.db = None

	def findPackageByPath(self, path: Path) -> sqlite3.Row:
		try:
			return next(self.db.execute("SELECT * FROM `packages` p where p.`path` = ?;", (str(path),)))
		except StopIteration:
			return None

	def registerPackage(self, name, path):
		res = self.db.execute("INSERT INTO `packages` (`name`, `path`) VALUES (:name, :path) ON CONFLICT (`path`) DO UPDATE SET `name` = `name`, `path` = `path`;", {"name": name, "path": str(path)})
		return res.lastrowid

	def registerTrigger(self, packageId, name):
		print("packageId", repr(packageId))
		res = self.db.execute("INSERT INTO `triggers` (`package`, `name`) VALUES (:packageId, :name) ON CONFLICT (`package`, `name`) DO UPDATE SET `package` = `package`, `name` = `name`;", {"packageId": packageId, "name": name})
		return res.lastrowid

	def setPackageEnabled(self, iD: int, status: bool) -> sqlite3.Cursor:
		return self.db.execute("UPDATE `packages` SET `status` = :status WHERE `id` = :id;", {"id": iD, "status": status})

	def setTriggerEnabled(self, iD: int, status: bool) -> sqlite3.Cursor:
		print('UPDATE `triggers` SET `status` = ' + repr(status) + ' WHERE `id` = ' + repr(iD) + ';')
		return self.db.execute("UPDATE `triggers` SET `status` = :status WHERE `id` = :id;", {"id": iD, "status": status})

	def unregisterTriggerById(self, iD):
		print('delete from `triggers` where `id` = "' + str(iD) + '";')
		return self.db.execute("delete from `triggers` where `id` = :triggerId;", {"triggerId": iD})

	def unregisterPackageTriggersByParentId(self, iD):
		return self.db.execute("delete from `triggers` where `package` = :packageId;", {"packageId": iD})

	def unregisterPackageById(self, iD):
		print('delete from `packages` where `id` = ' + str(iD) + '";')
		return self.db.execute("delete from `packages` where `id` = :packageId;", {"packageId": iD})

	def findTriggerByModuleAndName(self, packageId: int, name: str) -> sqlite3.Row:
		try:
			return next(self.db.execute("SELECT * FROM `triggers` t where t.`package` = ? AND name = ?;", (packageId, name)))
		except StopIteration:
			return None

	def findConditionsByTrigger(self, triggerId: int):
		res = list(self.db.execute("SELECT * FROM `conditions` t where t.`package` = ?;", (triggerId,)))
		return res

	def getTables(self) -> typing.Iterator[str]:
		for tr in self.db.execute('select `name` from `sqlite_master` where `type` = "table";',):
			yield tr[0]

	def drop(self):
		for tableName in DB_SCHEMA:
			try:
				self.db.executescript("DROP TABLE " + tableName + ";")
			except sqlite3.OperationalError:
				pass

	def isInitialized(self) -> bool:
		curTables = set(self.getTables())
		for tableName in DB_SCHEMA:
			if tableName not in curTables:
				return False
		return True

	def __enter__(self) -> "AuthDB":
		needCreate = False
		if not self.db:
			needCreate = needCreate and not self.dbPath.exists()
			dbDir = self.dbPath.parent
			dbDir.mkdir(parents=True, exist_ok=True)
			self.db = sqlite3.connect(str(self.dbPath))
			self.db.row_factory = sqlite3.Row
			self.db.execute("PRAGMA foreign_keys = ON;")
			if not self.isInitialized():
				self.initDB()

		if needCreate:
			self.initDB()

		return self

	def initDB(self):
		self.drop()
		self.initSchema()

	def commit(self) -> None:
		self.db.commit()

	def initSchema(self):
		for name, ddl in DB_SCHEMA.items():
			self.db.executescript("CREATE TABLE `" + name + "` (" + ddl + ");")
		self.commit()

	def __exit__(self, *args, **kwargs) -> None:
		self.commit()
		self.db.close()
		self.db = None
