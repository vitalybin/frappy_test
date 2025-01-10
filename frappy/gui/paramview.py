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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************


from frappy.gui.qt import QLabel, QSizePolicy, QWidget

from frappy.gui.util import loadUi


class ParameterView(QWidget):

    def __init__(self, node, module, parameter, parent=None):
        super().__init__(parent)
        loadUi(self, 'paramview.ui')
        self._node = node
        self._module = module
        self._parameter = parameter

        self._propWidgets = {}  # widget cache do avoid garbage collection

        self.paramNameLabel.setText(f"{module}:{parameter}")
        self._initParameterWidgets()

        # self._node.newData.connect(self._updateValue)

    def _initParameterWidgets(self):
        # initValues = self._node.queryCache(self._module) #? mix live data?
        row = 0

        font = self.font()
        font.setBold(True)

        props = self._node._getDescribingParameterData(self._module,
                                                       self._parameter)
        for prop in sorted(props):
            label = QLabel(prop + ':')
            label.setFont(font)
            label.setSizePolicy(QSizePolicy.Policy.Minimum,
                                QSizePolicy.Policy.Preferred)

            # make 'display' label
            view = QLabel(str(props[prop]))
            view.setFont(self.font())
            view.setSizePolicy(QSizePolicy.Policy.Expanding,
                               QSizePolicy.Policy.Preferred)
            view.setWordWrap(True)

            self.propertyGroupBox.layout().addWidget(label, row, 0)
            self.propertyGroupBox.layout().addWidget(view, row, 1)

            self._propWidgets[prop] = (label, view)

            row += 1

    def _updateValue(self, module, parameter, value):
        if module != self._module:
            return

        self._paramWidgets[parameter][1].currentLineEdit.setText(str(value[0]))
