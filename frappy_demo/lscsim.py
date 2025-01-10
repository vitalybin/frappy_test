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
"""a very simple simulator for a LakeShore

Model 370: parameters are stored, but no cryo simulation
Model 336: heat exchanger on channel A with loop 1, sample sensor on channel B
"""

from frappy.modules import Communicator


class Ls370Sim(Communicator):
    CHANNEL_COMMANDS = [
        ('RDGR?%d', '200.0'),
        ('RDGST?%d', '0'),
        ('RDGRNG?%d', '0,5,5,0,0'),
        ('INSET?%d', '1,5,5,0,0'),
        ('FILTER?%d', '1,5,80'),
    ]
    OTHER_COMMANDS = [
        ('*IDN?', 'LSCI,MODEL370,370184,05302003'),
        ('SCAN?', '3,1'),
        ('*OPC?', '1'),
    ]
    pollinterval = 1

    CHANNELS = list(range(1, 17))
    data = ()

    def earlyInit(self):
        super().earlyInit()
        self.data = dict(self.OTHER_COMMANDS)
        for fmt, v in self.CHANNEL_COMMANDS:
            for chan in self.CHANNELS:
                self.data[fmt % chan] = v

    def doPoll(self):
        super().doPoll()
        self.simulate()

    def simulate(self):
        # not really a simulation. just for testing RDGST
        for channel in self.CHANNELS:
            _, _, _, _, excoff = self.data[f'RDGRNG?{channel}'].split(',')
            if excoff == '1':
                self.data[f'RDGST?{channel}'] = '6'
            else:
                self.data[f'RDGST?{channel}'] = '0'
        for chan in self.CHANNELS:
            prev = float(self.data['RDGR?%d' % chan])
            # simple simulation: exponential convergence to 100 * channel number
            # using a weighted average
            self.data['RDGR?%d' % chan] = '%g' % (0.99 * prev + 0.01 * 100 * chan)

    def communicate(self, command):
        self.comLog(f'> {command}')

        chunks = command.split(';')
        reply = []
        for chunk in chunks:
            if '?' in chunk:
                chunk = chunk.replace('? ', '?')
                reply.append(self.data[chunk])
            else:
                for nqarg in (1, 0):
                    if nqarg == 0:
                        qcmd, arg = chunk.split(' ', 1)
                        qcmd += '?'
                    else:
                        qcmd, arg = chunk.split(',', nqarg)
                        qcmd = qcmd.replace(' ', '?', 1)
                    if qcmd in self.data:
                        self.data[qcmd] = arg
                        break
        reply = ';'.join(reply)
        self.comLog(f'< {reply}')
        return reply


class Ls336Sim(Ls370Sim):
    CHANNEL_COMMANDS = [
        ('KRDG?%s', '295.0'),
        ('RDGST?%s', '0'),
    ]
    OTHER_COMMANDS = [
        ('*IDN?', 'LSCI,MODEL370,370184,05302003'),
        ('RANGE?1', '0'),
        ('SETP?1', '0'),
        ('CLIMIT?1', ''),
        ('CSET?1', ''),
        ('CMODE?1', ''),
        ('*OPC?', '1'),
    ]

    CHANNELS = 'ABCD'

    vti = 295
    sample = 295

    def simulate(self):
        # simple temperature control on channel A:
        range_ = int(self.data['RANGE?1'])
        setp = float(self.data['SETP?1'])
        if range_:
            # heater on: approach setpoint with 20 sec time constant
            self.vti = max(self.vti - 0.1, self.vti + (setp - self.vti) * 0.05)
        else:
            # heater off 0.1/sec cool down
            self.vti = max(1.5, self.vti - 0.1)
        # sample approaching setpoint with 10 sec time constant, but with some
        # systematic heat loss towards 150 K
        self.sample = self.sample + (self.vti + (150 - self.vti) * 0.01 - self.sample) * 0.1
        self.data['KRDG?A'] = str(round(self.vti, 3))
        self.data['KRDG?B'] = str(round(self.sample, 3))
