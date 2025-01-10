#!/usr/bin/env python
# *****************************************************************************
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
# *****************************************************************************
"""Andeen Hagerling capacitance bridge

two modules: the capacitance itself and the loss angle

in the configuration file, only the capacitance module needs to be configured,
while the loss module will be created automatically.

the name of the loss module may be configured, or disabled by choosing
an empty name
"""

from frappy.core import FloatRange, HasIO, Parameter, Readable, StringIO, nopoll, \
    Attached, Property, StringType
from frappy.dynamic import Pinata


class Ah2700IO(StringIO):
    end_of_line = '\r\n'
    timeout = 5


class Capacitance(HasIO, Pinata, Readable):
    value = Parameter('capacitance', FloatRange(unit='pF'))
    freq = Parameter('frequency', FloatRange(unit='Hz'), readonly=False, default=0)
    voltage = Parameter('voltage', FloatRange(unit='V'), readonly=False, default=0)
    loss_name = Property('''name of loss module (default: <name>_loss)

                         configure '' to disable the creation of the loss module
                         ''',
                         StringType(), default='$_loss')

    ioClass = Ah2700IO
    loss = 0  # not a parameter

    def scanModules(self):
        if self.loss_name:
            # if loss_name is not empty, we tell the framework to create
            # a module for the loss with this name, and config below
            yield self.loss_name.replace('$', self.name), {
                'cls': Loss,
                'description': f'loss value of {self.name}',
                'cap': self.name}

    def parse_reply(self, reply):
        if reply.startswith('SI'):  # this is an echo
            self.communicate('SERIAL ECHO OFF')
            reply = self.communicate('SI')
        if not reply.startswith('F='):  # this is probably an error message like "LOSS TOO HIGH"
            self.status = self.Status.ERROR, reply
            return self.value
        self.status = self.Status.IDLE, ''
        # examples of replies:
        # 'F= 1000.0  HZ C= 0.000001    PF L> 0.0         DS V= 15.0     V'
        # 'F= 1000.0  HZ C= 0.0000059   PF L=-0.4         DS V= 15.0     V OVEN'
        # 'LOSS TOO HIGH'
        # make sure there is always a space after '=' and '>'
        # split() ignores multiple white space
        reply = reply.replace('=', '= ').replace('>', '> ').split()
        _, freq, _, _, cap, _, _, loss, lossunit, _, volt = reply[:11]
        self.freq = freq
        self.voltage = volt
        if lossunit == 'DS':
            self.loss = loss
        else:  # the unit was wrong, we want DS = tan(delta), not NS = nanoSiemens
            reply = self.communicate('UN DS').split()  # UN DS returns a reply similar to SI
            try:
                self.loss = reply[7]
            except IndexError:
                pass  # don't worry, loss will be updated next time
        return cap

    def read_value(self):
        return self.parse_reply(self.communicate('SI'))  # SI = single trigger

    @nopoll
    def read_freq(self):
        self.read_value()
        return self.freq

    @nopoll
    def read_voltage(self):
        self.read_value()
        return self.voltage

    def write_freq(self, value):
        self.value = self.parse_reply(self.communicate(f'FR {value:g};SI'))
        return self.freq

    def write_voltage(self, value):
        self.value = self.parse_reply(self.communicate(f'V {value:g};SI'))
        return self.voltage


class Loss(Readable):
    cap = Attached()
    value = Parameter('loss', FloatRange(unit='deg'), default=0)

    def initModule(self):
        super().initModule()
        self.cap.registerCallbacks(self, ['status'])  # auto update status

    def update_value(self, _):
        # value is always changed shortly after loss
        self.value = self.cap.loss

    @nopoll
    def read_value(self):
        self.cap.read_value()
        return self.cap.loss
