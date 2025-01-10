Node('simple_node',
     'Simplenode for test purpose\n\n'
     'Collection of functionalities needed for the analysis of the gas after and before the catalytic process.',
      'tcp://10804',
    
)  # you might choose any port number > 1024
Mod('simplen',  # the name of the module
    'frappy_Rachit.simple_node.SimpleNode',  # the class used for communication
    'SimpleNode',  # a description
    value= 1  # the serial connection
)    
    
