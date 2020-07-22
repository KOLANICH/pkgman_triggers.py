import typing

from PySide2.QtCore import Qt, Signal  # pylint:disable=no-name-in-module
from PySide2.QtWidgets import QApplication, QBoxLayout, QHeaderView, QTreeWidget, QTreeWidgetItem, QWidget, QMainWindow, QDockWidget, QToolBar, QStyle, QAction, QCheckBox, QWhatsThis  # pylint:disable=no-name-in-module

from . import TriggerManager
from .triggers import Module, Trigger, TemporaryID
from .util import universalValues

from .defaults import configPath

class Settings:
	__slots__ = ("autoRemove", "autoEnable", "filePath")

	def __init__(self):
		self.autoRemove = True
		self.autoEnable = False
		self.filePath = configPath

unregisteredText = "Unregistered"

class GuiEditor(QMainWindow):
	#__slots__ = ("treeWgt", "settingsWgt", "settings")

	def __init__(self, parent=None) -> None:
		super().__init__(parent)

		self.settings = Settings()

		dockableWindowsFeatures = QDockWidget.DockWidgetFeatures(QDockWidget.AllDockWidgetFeatures & ~QDockWidget.DockWidgetClosable)
		dockableWindowsAreas = Qt.DockWidgetAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

		self.setWindowTitle("pkgman_widgets GUI")

		self.treeWgt = OurTreeWidget("triggers", self.settings, self)
		self.addDockWidget(Qt.TopDockWidgetArea, self.treeWgt)
		self.treeWgt.setAllowedAreas(dockableWindowsAreas)
		self.treeWgt.setFeatures(dockableWindowsFeatures)

		#self.setCentralWidget(QWidget(self))

		self.settingsWgt = OurToolbar("Settings", self.settings, self)
		self.addToolBar(Qt.BottomToolBarArea, self.settingsWgt)
		#self.settingsWgt.setFeatures(dockableWindowsFeatures)

		self.settingsWgt.cleanupBtnTriggered.connect(self.treeWgt.cleanup)
		self.settingsWgt.refreshBtnTriggered.connect(self.treeWgt.refresh)

		self.updateGeometry()


class OurToolbar(QToolBar):
	__slots__ = ("tm", "tb", "cleanupBtn", "autoDeleteCbx", "autoEnableCbx", "openBtn", "settings")
	def __init__(self, name: str, settings: Settings, parent: QMainWindow) -> None:
		super().__init__(name, parent)
		self.settings = settings

		trashIcon = QApplication.style().standardIcon(QStyle.SP_TrashIcon)
		reloadIcon = QApplication.style().standardIcon(QStyle.SP_BrowserReload)
		openIcon = QApplication.style().standardIcon(QStyle.SP_DialogOpenButton)

		self.cleanupBtn = QAction("♻️", self)
		self.cleanupBtn.setToolTip("Cleanup")
		self.cleanupBtn.setWhatsThis("Recreate the database from the memory representation, cleaning the garbage")

		self.refreshBtn = QAction(reloadIcon, "&Refresh", self)
		self.openBtn = QAction(openIcon, "&Open DB", self)
		self.openBtn.setWhatsThis("Set the path of the the file to load.")

		self.autoDeleteCbx = QCheckBox("Remove Automatically", self)
		self.autoDeleteCbx.setChecked(Qt.CheckState.Checked if self.settings.autoRemove else Qt.CheckState.Unchecked)
		self.autoDeleteCbx.setWhatsThis("Automatically remove disabled stuff from the database.")

		self.autoEnableCbx = QCheckBox("Enable children automatically", self)
		self.autoEnableCbx.setChecked(Qt.CheckState.Checked if self.settings.autoEnable else Qt.CheckState.Unchecked)
		self.autoDeleteCbx.setWhatsThis("Automatically enable children when enabling parents.")

		self.addAction(self.cleanupBtn)
		self.addAction(self.refreshBtn)
		self.addAction(self.openBtn)
		self.addWidget(self.autoDeleteCbx)
		self.addWidget(self.autoEnableCbx)
		self.autoDeleteCbx.stateChanged.connect(self.autoDeleteCbxProcessor)
		self.cleanupBtn.triggered.connect(self.cleanupBtnTriggered)
		self.refreshBtn.triggered.connect(self.refreshBtnTriggered)

		self.updateGeometry()

	refreshBtnTriggered = Signal()
	cleanupBtnTriggered = Signal()

	def autoDeleteCbxProcessor(self, state):
		state = Qt.CheckState(state)
		self.settings.autoRemove = bool(state)

class OurTreeWidget(QDockWidget):
	#__slots__ = ("tm", "tree", "layout", "settings")
	def __init__(self, name: str, settings: Settings, parent: QMainWindow) -> None:
		super().__init__(name, parent)
		self.tm = None
		self.settings = settings

		self.tree = QTreeWidget(self)
		self.tree.setDisabled(True)
		self.tree.blockSignals(True);
		self.setWidget(self.tree)

		self.tree.setHeaderLabels(("ID", "Name", "Path", "Type"))
		self.tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)

		self.refresh()

		self.tree.itemChanged.connect(self.treeItemChanged)
		self.updateGeometry()

	def close(self):
		self.tree.blockSignals(True);
		self.tree.setDisabled(True)
		self.tree.clear()
		if self.tm:
			self.tm.__exit__(None, None, None)
			self.tm = None

	def open(self):
		self.close()
		self.tm = TriggerManager().__enter__()
		self.processModuleCollection(self.tree, self.tm.registeredModules, lambda m: str(m.id))
		self.processModuleCollection(self.tree, self.tm.unknownModules, lambda m: unregisteredText)
		self.adjustSize()
		self.tree.setDisabled(False)
		self.tree.blockSignals(False);

	def refresh(self):
		self.open()

	def cleanup(self):
		print("cleanup method called")

	def treeItemChanged(self, item: QTreeWidgetItem, column: int) -> None:  # pylint:disable=unused-argument
		d = item.data(0, Qt.UserRole)
		cs = item.checkState(0)

		self.tree.blockSignals(True)
		if isinstance(d, Trigger):
			m = item.parent().data(0, Qt.UserRole)
			assert isinstance(m, Module)
			res = self.triggerChanged(item, d, m, cs)
		if isinstance(d, Module):
			res = self.moduleChanged(item, d, cs)
		self.tree.blockSignals(False)
		return res

	def _removeTrigger(self, item, t):
		if t.registered:
			self.tm.unregisterTrigger(t)
			item.setCheckState(0, Qt.Unchecked)
			item.setText(0, unregisteredText)

	def triggerChanged(self, item, t, m, cs):
		print("triggerChanged", t, cs)
		if cs == Qt.CheckState.PartiallyChecked:
			pass
		else:
			if cs == Qt.CheckState.Checked:
				self.ensureTriggerRegistered(item, m, t)
				self.tm.setTriggerEnabled(t, True)
			elif cs == Qt.CheckState.Unchecked:
				if self.settings.autoRemove:
					self._removeTrigger(item, t)
				else:
					self.tm.setTriggerEnabled(t, False)
			else:
				raise ValueError(cs)
			self.tm.db.commit()

	def ensureTriggerRegistered(self, item, m, t):
		if not t.registered:
			self.registerTrigger(item, m, t)

	def registerTrigger(self, item, m, t):
		self.ensureModuleRegistered(item.parent(), m)
		self.tm.registerTrigger(m, t.id)
		item.setText(0, str(t.id))

	def registerModule(self, item, m):
		self.tm.registerPackage(m.id)
		item.setText(0, str(m.id))

	def ensureModuleRegistered(self, item, m):
		if not m.registered:
			self.registerModule(item, m)

	def moduleChanged(self, item, m, cs):
		print("moduleChanged", m, cs)
		if cs == Qt.CheckState.PartiallyChecked:
			pass
		else:
			if cs == Qt.CheckState.Checked:
				self.ensureModuleRegistered(item, m)
				self.tm.setPackageEnabled(m, True)
			elif cs == Qt.CheckState.Unchecked:
				if self.settings.autoRemove:
					for childNo in range(item.childCount()):
						el = item.child(childNo)
						trigger = el.data(0, Qt.UserRole)
						self._removeTrigger(el, trigger)
					self.tm.unregisterPackage(m)
					item.setText(0, unregisteredText)
					item.setCheckState(0, Qt.Unchecked)
				else:
					self.tm.setPackageEnabled(m, False)
			else:
				raise ValueError(cs)
			self.tm.db.commit()

	def processTriggersCollection(self, moduleItem, coll: typing.Mapping[int, Trigger], idGenerator):
		for t in universalValues(coll):
			triggerItem = QTreeWidgetItem(moduleItem)
			triggerItem.setFlags(triggerItem.flags() | Qt.ItemIsUserCheckable)
			triggerItem.setText(0, idGenerator(t))
			triggerItem.setText(1, t.internalName)
			triggerItem.setText(3, str(t.__class__.__name__))
			triggerItem.setCheckState(0, Qt.CheckState.Checked if t.status else Qt.CheckState.Unchecked)
			triggerItem.setData(0, Qt.UserRole, t)

	def processModuleCollection(self, tree: QTreeWidget, coll: typing.Mapping[int, Module], idGenerator: typing.Callable) -> None:
		for m in universalValues(coll):
			moduleItem = QTreeWidgetItem(tree)
			moduleItem.setText(0, idGenerator(m))
			moduleItem.setText(1, m.name)
			moduleItem.setText(2, str(m.path))
			moduleItem.setText(3, str(m.__class__.__name__))
			moduleItem.setExpanded(True)
			moduleItem.setFlags((moduleItem.flags() & ~Qt.ItemIsAutoTristate) | Qt.ItemIsUserCheckable)

			moduleItem.setData(0, Qt.UserRole, m)
			moduleItem.setCheckState(0, Qt.CheckState.Checked if m.status else Qt.CheckState.Unchecked)

			self.processTriggersCollection(moduleItem, m.registeredTriggers, lambda t: str(t.id))
			self.processTriggersCollection(moduleItem, m.unknownTriggers, lambda t: unregisteredText)


def makeApp() -> int:
	app = QApplication()
	w = GuiEditor()
	w.show()
	return app.exec_()
