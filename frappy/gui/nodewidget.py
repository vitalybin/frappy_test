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
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************

from collections import OrderedDict

from frappy.gui.qt import QCursor, QIcon, QInputDialog, QMenu, QSettings, \
    QVBoxLayout, QWidget, pyqtSignal

from frappy.gui.console import Console
from frappy.gui.moduleoverview import ModuleOverview
from frappy.gui.modulewidget import ModuleWidget
from frappy.gui.paramview import ParameterView
from frappy.gui.plotting import getPlotWidget
from frappy.gui.util import Colors, loadUi


class NodeWidget(QWidget):
    noPlots = pyqtSignal(bool)
    consoleTextSent = pyqtSignal(str)

    def __init__(self, node, parent=None):
        super().__init__(parent)
        loadUi(self, 'nodewidget.ui')

        self._node = node
        self._node.stateChange.connect(self._set_node_state)

        self.detailed = False
        self._modules = OrderedDict()
        self._detailedParams = {}
        self._activePlots = {}

        self.top_splitter.setStretchFactor(0, 2)
        self.top_splitter.setStretchFactor(1, 10)
        self.top_splitter.setSizes([180, 500])

        self.middle_splitter.setCollapsible(
            self.middle_splitter.indexOf(self.view), False)
        self.middle_splitter.setStretchFactor(0, 20)
        self.middle_splitter.setStretchFactor(1, 1)

        self.infobox_splitter.setStretchFactor(0, 3)
        self.infobox_splitter.setStretchFactor(1, 2)

        self.consoleWidget.setTitle('Console')
        cmd = Console(node, self.consoleWidget)
        cmd.msgLineEdit.sentText.connect(self.consoleTextSent.emit)
        self.consoleWidget.replaceWidget(cmd)

        viewLayout = self.viewContent.layout()
        for module in node.modules:
            widget = ModuleWidget(node, module, self.view)
            widget.plot.connect(lambda param, module=module:
                                self.plotParam(module, param))
            widget.plotAdd.connect(lambda param, module=module:
                                   self._plotPopUp(module, param))
            widget.paramDetails.connect(self.showDetailedParam)
            widget.showDetails(self.detailed)
            self.noPlots.connect(widget.plotsPresent)
            self._modules[module] = widget
            self._detailedParams[module] = {}
            for param in node.getParameters(module):
                view = ParameterView(node, module, param)
                view.setWindowTitle(f'{self._node.equipmentId}:{module}:{param} - Properties')
                self._detailedParams[module][param] = view
            viewLayout.addWidget(widget)

        self._initNodeInfo()

    def _initNodeInfo(self):
        self.tree = ModuleOverview(self._node)
        infolayout = QVBoxLayout()
        infolayout.setContentsMargins(0, 0, 0, 0)
        infolayout.addWidget(self.tree)
        self.infotree.setLayout(infolayout)
        # disabled until i find a way to deselect and go back to overview
        self.tree.itemChanged.connect(self.changeViewContent)
        self.tree.customContextMenuRequested.connect(self._treeContextMenu)

        self.descriptionEdit.setPlainText(
            self._node.properties.get('description', 'no description available'))
        self.hostLabel.setText(self._node.conn.uri)
        self.protocolLabel.setText(
            # insert some invisible spaces to get better wrapping
            self._node.conn.secop_version.replace(',', ',\N{ZERO WIDTH SPACE}'))

    def _set_node_state(self, nodename, online, state):
        p = self.palette()
        if online:
            p.setColor(self.backgroundRole(), Colors.palette.window().color())
            self.tree.setToReconnected()
        else:
            p.setColor(self.backgroundRole(), Colors.colors['orange'])
            # TODO: reset this for non-status modules!
            self.tree.setToDisconnected()
        self.setPalette(p)

    def _rebuildAdvanced(self, advanced):
        self.detailed = advanced
        self.tree._rebuildAdvanced(advanced)
        for m in self._modules.values():
            m.showDetailsBtn.setChecked(advanced)

    def getSecNode(self):
        return self._node

    def changeViewContent(self, module, param):
        if module == '' and param == '':
            return  # for now, don't do anything when resetting selection
        if param == '':
            widget = self._modules[module].moduleName
        else:
            widget = self._modules[module]._paramWidgets[param][0]
        self.view.ensureWidgetVisible(widget)
        settings = QSettings()
        if settings.value('highlightanimation', True, bool):
            widget.triggerAnimation()

    def showDetailedParam(self, module, param):
        self._detailedParams[module][param].show()

    def _treeContextMenu(self, pos):
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        item = self.tree.itemFromIndex(index)

        menu = QMenu()
        opt_plot = menu.addAction('Plot')
        opt_plot.setIcon(QIcon(':/icons/plot'))
        menu_plot_ext = menu.addMenu("Plot with...")
        menu_plot_ext.setIcon(QIcon(':/icons/plot'))
        if not self._activePlots:
            menu_plot_ext.setEnabled(False)
        else:
            for (m, p), plot in self._activePlots.items():
                opt_ext = menu_plot_ext.addAction(f"{m}:{p}")
                opt_ext.triggered.connect(
                        lambda plot=plot: self._requestPlot(item, plot))

        menu.addSeparator()
        opt_clear = menu.addAction('Clear Selection')
        opt_plot.triggered.connect(lambda: self._requestPlot(item))
        opt_clear.triggered.connect(self.tree.clearTreeSelection)
        # menu.exec(self.mapToGlobal(pos))
        menu.exec(QCursor.pos())

    def _requestPlot(self, item, plot=None):
        module = item.module
        param = item.param or 'value'
        self.plotParam(module, param, plot)

    def _plotPopUp(self, module, param):
        plots = {'%s -> %s' % mp: mp for mp in self._activePlots}
        dialog = QInputDialog()
        # dialog.setInputMode()
        dialog.setOption(
            QInputDialog.InputDialogOption.UseListViewForComboBoxItems)
        dialog.setComboBoxItems(plots.keys())
        dialog.setTextValue(list(plots)[0])
        dialog.setWindowTitle(f'Plot {param} with...')
        dialog.setLabelText('')

        if dialog.exec() == QInputDialog.DialogCode.Accepted:
            item = dialog.textValue()
            self.plotParam(module, param, self._activePlots[plots[item]])

    def plotParam(self, module, param, plot=None):
        # - liveness?
        # - better plot window management?

        # only allow one open plot per parameter TODO: change?
        if (module, param) in self._activePlots:
            return
        if plot:
            plot.addCurve(self._node, module, param)
            plot.setCurveColor(module, param,
                               Colors.colors[len(plot.curves) % 6])
        else:
            plot = getPlotWidget(self)
            plot.addCurve(self._node, module, param)
            plot.setCurveColor(module, param, Colors.colors[1])
            self._activePlots[(module, param)] = plot
            plot.closed.connect(lambda: self._removePlot(module, param))
            plot.show()

        self.noPlots.emit(len(self._activePlots) == 0)

        # initial datapoint
        cache = self._node.queryCache(module)
        if param in cache:
            plot.update(module, param, cache[param])

    def _removePlot(self, module, param):
        self._activePlots.pop((module, param))
        self.noPlots.emit(len(self._activePlots) == 0)
