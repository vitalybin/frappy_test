# *****************************************************************************
# Copyright (c) 2015-2024 by the authors, see LICENSE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Module authors:
#   Jens Krüger <jens.krueger@frm2.tum.de>
#
# *****************************************************************************

"""Detachable TabWidget, taken from NICOS GUI TearOffTabBar."""

from frappy.gui.qt import QApplication, QCursor, QDrag, QEvent, QMainWindow, \
    QMimeData, QMouseEvent, QPixmap, QPoint, QPointF, QSize, QStyle, \
    QStyleOptionTab, QStylePainter, Qt, QTabBar, QTabWidget, QWidget, \
    pyqtSignal, pyqtSlot

# def findTab(tab, w):
#     widget = w
#     while True:
#         parent = widget.parent()
#         if not parent:
#             return False
#         widget = parent
#         if isinstance(widget, AuxiliarySubWindow) and tab == widget:
#             return True
#     return False
#
#
# def findTabIndex(tabwidget, w):
#     for i in range(len(tabwidget)):
#         if findTab(tabwidget.widget(i), w):
#             return i
#     return None


class TearOffTabBar(QTabBar):

    tabDetached = pyqtSignal(object, object)
    tabMoved = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QTabBar.__init__(self, parent)
        self.setAcceptDrops(True)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setSelectionBehaviorOnRemove(QTabBar.SelectionBehavior.SelectLeftTab)
        self.setMovable(False)
        self._dragInitiated = False
        self._dragDroppedPos = QPoint()
        self._dragStartPos = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragStartPos = event.pos()
        self._dragInitiated = False
        self._dragDroppedPos = QPoint()
        QTabBar.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        if not event.buttons() & Qt.MouseButton.LeftButton:
            return
        if not self._dragStartPos.isNull() and \
           self.tabAt(self._dragStartPos) != -1 and \
           (event.pos() - self._dragStartPos).manhattanLength() \
           < QApplication.startDragDistance():
            self._dragInitiated = True
        if (event.buttons() == Qt.MouseButton.LeftButton) and \
            self._dragInitiated and \
            not self.geometry().contains(event.pos()):
            finishMoveEvent = QMouseEvent(QEvent.Type.MouseMove,
                                          QPointF(event.pos()),
                                          Qt.MouseButton.NoButton,
                                          Qt.MouseButton.NoButton,
                                          Qt.KeyboardModifier.NoModifier)
            QTabBar.mouseMoveEvent(self, finishMoveEvent)

            drag = QDrag(self)
            mimedata = QMimeData()
            mimedata.setData('action', b'application/tab-detach')
            drag.setMimeData(mimedata)

            pixmap = self.parentWidget().currentWidget().grab()
            pixmap = pixmap.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)
            drag.setPixmap(pixmap)
            drag.setDragCursor(QPixmap(), Qt.DropAction.LinkAction)

            dragged = drag.exec(Qt.DropAction.MoveAction)
            if dragged == Qt.DropAction.IgnoreAction:
                # moved outside of tab widget
                event.accept()
                self.tabDetached.emit(self.tabAt(self._dragStartPos),
                                      QCursor.pos())
            elif dragged == Qt.DropAction.MoveAction:
                # moved inside of tab widget
                if not self._dragDroppedPos.isNull():
                    event.accept()
                    self.tabMoved.emit(self.tabAt(self._dragStartPos),
                                       self.tabAt(self._dragDroppedPos))
                    self._dragDroppedPos = QPoint()
        else:
            QTabBar.mouseMoveEvent(self, event)

    def dragEnterEvent(self, event):
        mimedata = event.mimeData()
        formats = mimedata.formats()
        if 'action' in formats and \
           mimedata.data('action') == 'application/tab-detach':
            event.acceptProposedAction()
        QTabBar.dragEnterEvent(self, event)

    def dropEvent(self, event):
        self._dragDroppedPos = event.pos()
        event.acceptProposedAction()
        QTabBar.dropEvent(self, event)


class LeftTabBar(TearOffTabBar):
    def __init__(self, parent, text_padding):
        TearOffTabBar.__init__(self, parent)
        self.text_padding = text_padding

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionTab()

        for index in range(self.count()):
            self.initStyleOption(option, index)
            tabRect = self.tabRect(index)
            tabRect.moveLeft(10)
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabShape, option)
            text = self.tabText(index)
            painter.drawText(tabRect, Qt.AlignmentFlag.AlignVCenter |
                             Qt.TextFlag.TextDontClip |
                             Qt.TextFlag.TextShowMnemonic, text)

    def tabSizeHint(self, index):
        fm = self.fontMetrics()
        tabSize = fm.boundingRect(
            self.tabText(index) or 'Ag').size() + QSize(*self.text_padding)
        return tabSize


class TearOffTabWidget(QTabWidget):
    """Tab widget with detachable tabs.

    Detached tabs will reattach when closed.

    Options:

    * ``position`` (default top) -- sets the position of the tab selector.
      Choices are top or left.
    * ``margins`` (default (0, 6, 0, 0)) -- sets the margin around the tab item.
    * ``textpadding`` (default (20, 10)) -- sets the right padding and vertical
      padding for the text in the tab label.
    """

    class TabWidgetStorage:
        def __init__(self, index, widget, title, visible=True):
            self.index = index
            self.widget = widget
            self.title = title
            self.visible = visible
            self.detached = None

        def setDetached(self, detached):
            self.detached = detached

        def __repr__(self):
            return f'index {self.index}, widget {self.widget!r}, title {self.title},' \
                f' visible {self.visible!r}, detached {self.detached!r}'

    def __init__(self, item, window, menuwindow, parent=None):
        QTabWidget.__init__(self, parent)
        self.menuwindow = menuwindow
        # if item.options.get('position', 'top') == 'left':
        #     tabBar = LeftTabBar(self, item.options.get('textpadding', (20, 10)))
        #     self.setTabBar(tabBar)
        #     self.setTabPosition(QTabWidget.West)
        # else:
        #     tabBar = TearOffTabBar(self)
        #     self.setTabBar(tabBar)
        tabBar = TearOffTabBar(self)
        self.setTabBar(tabBar)

        self.setMovable(False)
        self.previousTabIdx = 0
        tabBar.tabDetached.connect(self.detachTab)
        tabBar.tabMoved.connect(self.moveTab)
        self.currentChanged.connect(self.tabChangedTab)
        self.tabIdx = {}
        # don't draw a frame around the tab contents
        self.setStyleSheet('QTabWidget:tab:disabled{width:0;height:0;'
                           'margin:0;padding:0;border:none}')
        self.setDocumentMode(True)
        # default: only keep margin at the top (below the tabs)
        # margins = item.options.get('margins', (0, 6, 0, 0))
        # for entry in item.children:
        #     self.addPanel(
        #         AuxiliarySubWindow(entry[1:], window, menuwindow, self,
        #                            margins), entry[0])

    def moveTab(self, from_ind, to_ind):
        w = self.widget(from_ind)
        text = self.tabText(from_ind)
        self.removeTab(from_ind)
        self.insertTab(to_ind, w, text)
        self.setCurrentIndex(to_ind)

    def _findFirstWindow(self, w):
        widget = w
        while True:
            parent = widget.parent()
            if not parent:
                break
            widget = parent
            if isinstance(widget, QMainWindow):
                break
        return widget

    def _tabWidgetIndex(self, widget):
        for i in range(self.tabBar().count()):
            if self.widget(i) == widget:
                return i
        return -1

    def tabInserted(self, index):
        w = self.widget(index)
        for i in self.tabIdx.values():
            if i.widget == w:
                return
        self.tabIdx[index] = self.TabWidgetStorage(index, self.widget(index),
                                                   self.tabText(index))

    def _setPanelToolbars(self, panel, visible):
        for tb in panel.getToolbars():
            tb.setVisible(visible)

    def _setPanelMenus(self, panel, visible):
        for m in panel.getMenus():
            m.menuAction().setVisible(visible)

    # @pyqtSlot(QWidget, bool)
    # def setWidgetVisibleSlot(self, widget, visible):
    #     w = self._findFirstWindow(widget)  # get widget which is related to tab
    #     for i in self.tabIdx.values():     # search for it in the list of tabs
    #         if i.widget == w:              # found
    #             if isinstance(widget, Panel):
    #                 if not visible or (visible and self.currentWidget() ==
    #                                    widget):
    #                     self._setPanelToolbars(widget, visible)
    #                     self._setPanelMenus(widget, visible)
    #             if visible:
    #                 if not i.visible:
    #                     newIndex = -1
    #                     for j in self.tabIdx.values():
    #                         if j.visible and j.index > i.index:
    #                             cIdx = self._tabWidgetIndex(j.widget)
    #                             if cIdx < i.index and cIdx != -1:
    #                                 newIndex = cIdx
    #                             else:
    #                                 newIndex = i.index
    #                             break
    #                     self.insertTab(newIndex, i.widget, i.title)
    #             else:
    #                 i.visible = False
    #                 index = self._tabWidgetIndex(i.widget)
    #                 self.removeTab(index)

    def _getPanel(self, widget):
        panel = widget
        if isinstance(widget, QMainWindow):  # check for main window type
            panel = widget.centralWidget()
            if panel and panel.layout():  # check for layout
                panel = panel.layout().itemAt(0).widget()
        return panel

    def detachTab(self, index, point):
        detachWindow = DetachedWindow(self.tabText(index).replace('&', ''),
                                      self.parentWidget())
        w = self.widget(index)
        for i in self.tabIdx.values():
            if i.widget == w:
                detachWindow.tabIdx = self.tabIdx[i.index].index
                self.tabIdx[i.index].detached = detachWindow
                break

        detachWindow.closed.connect(self.attachTab)

        tearOffWidget = self.widget(index)
        #panel = self._getPanel(tearOffWidget)
        #if not isinstance(panel, QTabWidget):
        #    panel.setWidgetVisible.disconnect(self.setWidgetVisibleSlot)
        #    panel.setWidgetVisible.connect(detachWindow.setWidgetVisibleSlot)
        tearOffWidget.setParent(detachWindow)

        if self.count() < 0:
            self.setCurrentIndex(0)

        # self._moveMenuTools(tearOffWidget)
        # self._moveActions(tearOffWidget, detachWindow)

        detachWindow.setWidget(tearOffWidget)
        detachWindow.resize(tearOffWidget.size())
        detachWindow.move(point)
        detachWindow.show()

    # def _moveMenuTools(self, widget):
    #     for p in widget.panels:
    #         if hasattr(p, 'menuToolsActions'):
    #             topLevelWindow = self.topLevelWidget(p)

    #             if hasattr(topLevelWindow, 'menuTools'):
    #                 for action in p.menuToolsActions:
    #                     topLevelWindow.menuTools.removeAction(action)

    #def _moveActions(self, widget, window):
    #    for p in widget.panels:
    #        for action in p.actions:
    #            action.setVisible(False)

    #        for menu in p.getMenus():
    #            action = window.menuBar().addMenu(menu)
    #            action.setVisible(True)

    #        for toolbar in p.getToolbars():
    #            toolbar.hide()
    #            topLevelWindow = self.topLevelWidget(p)
    #            topLevelWindow.removeToolBar(toolbar)

    #            window.addToolBar(toolbar)
    #            toolbar.show()

    def attachTab(self, detach_window):
        detach_window.closed.connect(self.attachTab)
        #detach_window.saveSettings(False)
        tearOffWidget = detach_window.centralWidget()
        #panel = self._getPanel(tearOffWidget)
        # if panel and not isinstance(panel, QTabWidget):
        #     panel.setWidgetVisible.disconnect(detach_window.setWidgetVisibleSlot)
        tearOffWidget.setParent(self)
        # if panel and not isinstance(panel, QTabWidget):
        #     panel.setWidgetVisible.connect(self.setWidgetVisibleSlot)

        #for p in tearOffWidget.panels:
        #    if hasattr(p, 'menuToolsActions'):
        #        topLevelWindow = self.topLevelWidget(self)

        #        if hasattr(topLevelWindow, 'menuTools'):
        #            for action in p.menuToolsActions:
        #                topLevelWindow.menuTools.removeAction(action)

        newIndex = -1

        for i in range(self.tabBar().count()):
            w = self.widget(i)
            for j in self.tabIdx.values():
                if j.widget == w and j.index > detach_window.tabIdx:
                    newIndex = i
                    break
            else:
                continue
            break

        if newIndex == -1:
            newIndex = self.tabBar().count()

        newIndex = self.insertTab(newIndex, tearOffWidget,
                                  detach_window.windowTitle())
        if newIndex != -1:
            self.setCurrentIndex(newIndex)

        idx = self.find_widget(tearOffWidget)
        self.tabIdx[idx].detached = None

    def tabChangedTab(self, index):
        # for i in range(self.count()):
        #     for p in self.widget(i).panels:
        #         for toolbar in p.getToolbars():
        #             self.menuwindow.removeToolBar(toolbar)
        #         for action in p.actions:
        #             action.setVisible(False)

        # if self.previousTabIdx < self.count():
        #     if self.widget(self.previousTabIdx):
        #         for p in self.widget(self.previousTabIdx).panels:
        #             if hasattr(p, 'menuToolsActions'):
        #                 topLevelWindow = self.topLevelWidget(p)

        #                 if hasattr(topLevelWindow, 'menuTools'):
        #                     for action in p.menuToolsActions:
        #                         topLevelWindow.menuTools.removeAction(action)

        # if self.widget(index):
        #     for p in self.widget(index).panels:
        #         p.getMenus()

        #         if hasattr(p, 'menuToolsActions'):
        #             topLevelWindow = self.topLevelWidget(p)

        #             if hasattr(topLevelWindow, 'menuTools'):
        #                 for action in p.menuToolsActions:
        #                     topLevelWindow.menuTools.addAction(action)

        #         for toolbar in p.getToolbars():
        #             if hasattr(self.menuwindow, 'toolBarWindows'):
        #                 self.menuwindow.insertToolBar(
        #                     self.menuwindow.toolBarWindows, toolbar)
        #             else:
        #                 self.menuwindow.addToolBar(toolbar)
        #             toolbar.show()

        #         for menu in p.actions:
        #             menu.setVisible(True)

        self.previousTabIdx = index

    def addPanel(self, widget, label):
        #sgroup = SettingGroup(label)
        #with sgroup as settings:
        #    detached = settings.value('detached', False, bool)
        index = len(self.tabIdx)
        self.tabIdx[index] = self.TabWidgetStorage(index, widget, label)
        #if not detached:
        index = self.addTab(widget, label)
        if not label or label.isspace():
            self.setTabEnabled(index, False)
        for i in self.tabIdx.values():  # search for it in the list of tabs
            if i.widget == widget:
                i.setDetached(None)
        #else:
        #    detachWindow = DetachedWindow(label.replace('&', ''),
        #                                  self.parentWidget())
        #    detachWindow.tabIdx = index
        #    detachWindow.setAttribute(Qt.WA_DeleteOnClose, True)
        #    self.tabIdx[index].setDetached(detachWindow)
        #    detachWindow.closed.connect(self.attachTab)

        #    panel = self._getPanel(widget)
        #    if panel and not isinstance(panel, QTabWidget):
        #        panel.setWidgetVisible.disconnect(self.setWidgetVisibleSlot)
        #        panel.setWidgetVisible.connect(
        #            detachWindow.setWidgetVisibleSlot)
        #    widget.setParent(detachWindow)

        #    self._moveMenuTools(widget)
        #    self._moveActions(widget, detachWindow)

        #    detachWindow.setWidget(widget)
        #    detachWindow.destroyed.connect(detachWindow.deleteLater)
        #    # with sgroup as settings:
        #    #     detachWindow.restoreGeometry(settings.value('geometry', '',
        #    #                                                 QByteArray))
        #    detachWindow.show()

    def find_widget(self, widget):
        for idx, tab in self.tabIdx.items():
            if tab.widget == widget:
                return idx
        return None

    def replace_widget(self, old_widget, new_widget, title=None):
        """If old_widget is a child of either a tab or a detached window, it will
        be replaced by new_widget"""
        idx = self.find_widget(old_widget)
        if not idx:
            return
        wstore = self.tabIdx[idx]
        if title:
            wstore.title = title
        if wstore.detached:
            wstore.detached.setWidget(new_widget)
        else:
            tabi = self._tabWidgetIndex(old_widget)
            self.removeTab(tabi)
            self.insertTab(tabi, new_widget, wstore.title)
        wstore.widget = new_widget

    def topLevelWidget(self, w):
        widget = w
        while True:
            parent = widget.parent()
            if not parent:
                break
            widget = parent
        return widget

    def close_current(self):
        self.tabCloseRequested.emit(self.currentIndex())


class DetachedWindow(QMainWindow):

    closed = pyqtSignal(object)

    def __init__(self, title, parent):
        self.tabIdx = -1
        QMainWindow.__init__(self, parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.NonModal)
        # self.sgroup = SettingGroup(title)
        # with self.sgroup as settings:
        #     loadBasicWindowSettings(self, settings)

    @pyqtSlot(QWidget, bool)
    def setWidgetVisibleSlot(self, widget, visible):
        self.setVisible(visible)

    def setWidget(self, widget):
        self.setCentralWidget(widget)
        widget.show()

    def closeEvent(self, event):
        # with self.sgroup as settings:
        #     settings.setValue('detached', False)
        self.closed.emit(self)
        self.deleteLater()

    def moveEvent(self, event):
        QMainWindow.moveEvent(self, event)
        # self.saveSettings()

    def resizeEvent(self, event):
        QMainWindow.resizeEvent(self, event)
        # self.saveSettings()

    # def saveSettings(self, detached=True):
    #     with self.sgroup as settings:
    #         settings.setValue('detached', detached)
    #         settings.setValue('geometry', self.saveGeometry())
    #         settings.setValue('windowstate', self.saveState())


def firstWindow(w):
    widget = w
    while True:
        parent = widget.parent()
        if not parent:
            widget = None
            break
        widget = parent
        if widget.isWindow():
            break
    return widget
