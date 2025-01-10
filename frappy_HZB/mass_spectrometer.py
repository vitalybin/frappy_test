import time


from frappy.datatypes import FloatRange, StringType, StructOf, ArrayOf,StatusType,EnumType
from frappy.lib import clamp, mkthread
from frappy.lib.enum import Enum
from frappy.modules import Command, Drivable, Parameter,Attached,Readable
from frappy.errors import IsErrorError, ReadFailedError, InternalError,   ImpossibleError, IsBusyError
from frappy.core import BUSY, IDLE
import numpy as np
import random
# test custom property (value.test can be changed in config file)


num_spec = 10

Mode = Enum('mode',
    MID_SCAN = 0,
    BAR_SCAN = 1

)    

Device = Enum('device',
    FARADAY = 0,
    SEM = 1
)



class MassSpectrometer(Readable):


    status = Parameter(datatype=StatusType(Readable, 'BUSY'))  
    
    value = Parameter("partial pressures of measured spectrum",
                      ArrayOf(FloatRange(0,1000)),
                      unit= "mbar",
                      readonly = True        
                          )
        
    mass = Parameter("mass numbers in sprectrum of value",
                     ArrayOf(FloatRange(0,1000)),
                             unit = 'amu',
                             readonly = True)
                     
    aquire_time = Parameter("time duration for aquisition of spectrum",
                            FloatRange(0,60),
                            default = 2,
                            unit = "s",
                            readonly = False)
    
    vacuum_pressure = Parameter("Pressure inside the measurement chamber",
                                FloatRange(0,2000),
                                default = 0,
                                unit = "mbar",
                                readonly = True
                                )
    
    mode = Parameter("indicates the current scan mode",
                        EnumType(Mode),
                        readonly = False,
                        default = 1)
    mid_descriptor = Parameter("Datastructure that describes an MID Scan. (massnumber and measurement device for each massnumber)",
                               StructOf(
                                   mass = ArrayOf(FloatRange(0.4,200),1,200),
                                   device = ArrayOf(EnumType(Device),minlen=1,maxlen=200)
                                   ),
                                   readonly = False,
                                   group = 'MID_SCAN',
                                   default = {'mass':[1,2,3],'device':[0,0,0]}
                                )
    
    measurement_device = Parameter("Selects the detector for a bar scan",
                                          EnumType(Device),
                                            group = 'BAR_SCAN',
                                            readonly = False,
                                            default = 0
                                          )
    
    start_mass = Parameter('Start mass number for a bar scan',
                           FloatRange(0.4,200),
                           unit = 'amu',
                           group = 'BAR_SCAN',
                           readonly = False,
                           default = 1)
    
    end_mass = Parameter('End mass number for a bar scan',
                        FloatRange(0.4,200),
                        unit = 'amu',
                        group = 'BAR_SCAN',
                        readonly = False,
                        default = 30)
    
    increment = Parameter('Mass increment between scans in a bar scan',
                               FloatRange(0,200),
                               unit = 'amu',
                               group = 'BAR_SCAN',
                               readonly = False,
                               default = 1)
    
    scan_cycle = Parameter('indicates if in single or continuous cycle mode',
                           EnumType("scan_cycle",{
                               'SINGLE':0,
                               'CONTINUOUS':1
                           }),
                           readonly = False,
                           default = 0)
    
    electron_energy = Parameter('The Electron energy is used to define the filament potential in the Ion Source. This is used to change the Appearance Potential of gasses with similar mass footprints so they can be looked at individually.',
                                FloatRange(0,200),
                                unit = 'V',
                                group = 'global_residual_gas_analysis_parameters',
                                default = 70
                                )
    emission = Parameter('The Emission current is the current which flows from the active filament to the Ion Source Cage. An increase in Emission Current causes an increase in peak intensity, can be used to increase/reduce the peak intensities.',
                         FloatRange(min=0),
                         unit = 'A',
                         group = 'global_residual_gas_analysis_parameters',
                         default = 250e-06)
    
    focus = Parameter('This is the voltage applied to the Focus plate. This is used to extract the positive Ions from the source and into the Mass Filter, and also to block the transmission of electrons.',
                      FloatRange(min=-1000,max=1000),
                      unit = 'V',
                      group = 'global_residual_gas_analysis_parameters',
                      default = -90)
    
    multiplier = Parameter('The voltage applied to the SEM detector; with a PIC this should be set so the SEM operates in the Plateau Region. With an Analogue system this should be set to 1000 gain, i.e. a scan in Faraday should be equal height using the SEM detector.',
                           FloatRange(min=0),
                           unit = 'V',
                           group = 'global_residual_gas_analysis_parameters',
                           default = 910)
    
    cage = Parameter('This is the Ion Source Cage voltage which controls the Ion Energy. The higher the Ion Energy the faster the Ions travel through the Mass Filter to the Detector, this reduces the oscillation effect caused by the RF which is applied to the filter.',
                     FloatRange(min= 0),
                     unit = 'V',
                     group = 'global_residual_gas_analysis_parameters',
                     default = 3)
    
    resolution = Parameter('The high mass peak width/valley adjustment used during set up and maintenance. Can also affect the low masses and should be adjusted in conjunction with the Delta-M.',
                           FloatRange(min= 0 ),
                           unit = '%',
                           group = 'global_residual_gas_analysis_parameters',
                           default = 0)
    
    delta_m = Parameter('The low mass peak width/valley adjustment used during set up and maintenance. Can also affect the high masses and should be adjusted in conjunction with the Resolution',
                        FloatRange(min= 0 ),
                        unit = '%',
                        group = 'global_residual_gas_analysis_parameters',
                        default = 0)
    
    start_range = Parameter('Contains the range used at the start of a scan.',
                            FloatRange(min=0),
                            unit = 'mbar',
                            group = 'acquisition_range',
                            readonly = True,
                            default = 1e-5)
    
    autorange_high = Parameter('The highest range to which the input device may autorange',
                        FloatRange(min=0),
                        unit = 'mbar',
                        group = 'acquisition_range',
                        readonly = True,
                        default = 1e-5)
    
    autorange_low = Parameter('The lowest range to which the input device may autorange',
                        FloatRange(min=0),
                        unit = 'mbar',
                        group = 'acquisition_range',
                        readonly = True,
                        default = 1e-10)
    
    settle = Parameter('Defines the time to allow the electronics to settle before the scan is started. Given as a percentage of the default settle time for the current range.',
                        FloatRange(min=0),
                        unit = '%',
                        group = 'acquisition_range',
                        readonly = True,
                        default = 100)
    
    dwell = Parameter('Defines the time used to acquire a single point in the scan. Given as a percentage of the default settle time for the current range.',
                        FloatRange(min=0),
                        unit = '%',
                        group = 'acquisition_range',
                        readonly = True,
                        default = 100)
    

    
    



    def initModule(self):
        super().initModule()
        self._stopflag = False
        self._thread = mkthread(self.thread)
        self.interface_classes = ['Triggerable','Readable']
    

    def read_status(self):
        # instead of asking a 'Hardware' take the value from the simulation
        return self.status
    

    def read_value(self):
        
        return self.spectrum
    
    def read_vacuum_pressure(self):
        return 1.0e-10 * random.randint(0,1)
    
    def write_start_mass(self,start_mass):
        self.start_mass = start_mass
        self.spectrum = self.getSpectrum(dummy = True)
        self.read_value()
        return self.start_mass
    
    def write_end_mass(self,end_mass):
        self.end_mass = end_mass
        self.spectrum = self.getSpectrum(dummy=True)
        self.read_value()
        return self.end_mass
        
        
    def write_increment(self,increment):
        self.increment = increment
        self.spectrum = self.getSpectrum(dummy=True)
        self.read_value()
        return self.increment

    
    def write_mid_descriptor(self,mid_descriptor):
        self.mid_descriptor = mid_descriptor
        self.spectrum = self.getSpectrum(dummy=True)
        self.read_value()
        return self.mid_descriptor
    
    def write_mode(self,mode):
        self.mode = mode
        self.spectrum = self.getSpectrum(dummy=True)
        self.read_value()
        return self.mode


    @Command(None, result=None)
    def stop(self):
        """cease driving, go to IDLE state"""
        self.go_flag = False
        self.status = self.Status.IDLE, 'Stopped'
        self.read_status()



    



    @Command()
    def go(self):
        """generate new spectrum"""
        if self.status[0] == BUSY:
            return

        self.status = self.Status.BUSY, 'reading Spectrum'
        self.go_flag = True



    def getSpectrum(self,dummy:bool = False) -> list[float]:
        if self.mode == Mode('BAR_SCAN'):
            self.mass = np.arange(start=self.start_mass,stop=self.end_mass+self.increment,step=self.increment).tolist()
            num_mass = len(self.mass)
            
            if dummy:
                return np.zeros(num_mass)
            
            print(np.random.randint(0,1000,num_mass).tolist())
            
            return np.random.randint(0,1000,num_mass).tolist()


            


        elif self.mode == Mode('MID_SCAN'):
            self.mass = self.mid_descriptor['mass']
            num_mass = len(self.mass)
            
            if dummy:
                return np.zeros(num_mass)
            
            print(np.random.randint(0,1000,num_mass).tolist())

            return np.random.randint(0,1000,num_mass).tolist()
            
      
        else:
            
            self.mass = np.random.randint(0,1000,num_mass).tolist()
            

            if dummy:
                return np.zeros(len(self.mass))

            return np.random.randint(0,1000,num_mass).tolist()
        


        


    def thread(self):
        self.spectrum = self.getSpectrum(dummy=True)
        self.go_flag = False

        self.status = self.Status.IDLE, ''
        while not self._stopflag:
            try:
                self.__sim()
            except Exception as e:
                self.log.exception(e)
                self.status = self.Status.ERROR, str(e)

    def __sim(self):

        # keep history values for stability check

        while not self._stopflag:

            if self.go_flag:
                time.sleep(self.aquire_time)
                self.spectrum = self.getSpectrum(dummy=False)
                if self.scan_cycle == 'SINGLE':
                    self.status = self.Status.IDLE, 'Spectrum finished'
                    self.go_flag = False
                self.read_value()
                
            time.sleep(0.1)
                
            
                
            



    def shutdownModule(self):
        # should be called from server when the server is stopped
        self._stopflag = True
        if self._thread and self._thread.is_alive():
            self._thread.join()

        

        


        
        