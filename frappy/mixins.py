# *****************************************************************************
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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************

from frappy.datatypes import BoolType, EnumType, Enum
from frappy.core import Parameter, Attached


class HasControlledBy:
    """mixin for modules with controlled_by

    in the :meth:`write_target` the hardware action to switch to own control should be done
    and in addition self.self_controlled() should be called
    """
    controlled_by = Parameter('source of target value', EnumType(members={'self': 0}), default=0)
    target = Parameter()  # make sure target is a parameter
    inputCallbacks = ()

    def register_input(self, name, deactivate_control):
        """register input

        :param name: the name of the module (for controlled_by enum)
        :param deactivate_control: a method on the input module to switch off control

        called by <controller module>.initModule
        """
        if not self.inputCallbacks:
            self.inputCallbacks = {}
        self.inputCallbacks[name] = deactivate_control
        prev_enum = self.parameters['controlled_by'].datatype.export_datatype()['members']
        # add enum member, using autoincrement feature of Enum
        self.parameters['controlled_by'].datatype = EnumType(Enum(prev_enum, **{name: None}))

    def self_controlled(self):
        """method to change controlled_by to self

        to be called from the write_target method
        """
        if self.controlled_by:
            self.controlled_by = 0  # self
            for deactivate_control in self.inputCallbacks.values():
                deactivate_control(self.name)

    def update_target(self, module, value):
        """update internal target value

        as write_target would switch to manual mode, the controlling module
        has to use this method to update the value

        override and super call, if other actions are needed
        """
        if self.controlled_by != module:
            deactivate_control = self.inputCallbacks.get(self.controlled_by)
            if deactivate_control:
                deactivate_control(module)
        self.target = value


class HasOutputModule:
    """mixin for modules having an output module

    in the :meth:`write_target` the hardware action to switch to own control should be done
    and in addition self.activate_control() should be called
    """
    # mandatory=False: it should be possible to configure a module with fixed control
    output_module = Attached(HasControlledBy, mandatory=False)
    control_active = Parameter('control mode', BoolType(), default=False)
    target = Parameter()  # make sure target is a parameter

    def initModule(self):
        super().initModule()
        if self.output_module:
            self.output_module.register_input(self.name, self.deactivate_control)

    def set_control_active(self, active):
        """to be overridden for switching hw control"""
        self.control_active = active

    def activate_control(self):
        """method to switch control_active on

        to be called from the write_target method
        """
        out = self.output_module
        if out:
            for name, deactivate_control in out.inputCallbacks.items():
                if name != self.name:
                    deactivate_control(self.name)
            out.controlled_by = self.name
        self.set_control_active(True)

    def deactivate_control(self, source=None):
        """called when another module takes over control

        registered to be called from the controlled module(s)
        """
        if self.control_active:
            self.set_control_active(False)
            self.log.warning(f'switched to manual mode by {source or self.name}')
