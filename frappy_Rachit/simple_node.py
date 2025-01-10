from frappy.core import Readable, Parameter, ScaledInteger
import random

class SimpleNode(Readable):
    value = Parameter(datatype=ScaledInteger(scale= 1,min = 0,max =100,))
    
    def read_value(self):
        return random.randint(1,9)*1 
