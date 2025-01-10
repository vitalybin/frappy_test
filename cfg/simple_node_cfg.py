Node('simple_node',  # a globally unique identification
     'Simplenode for test purpose\n\n',  # describes the node
      'tcp://10804',
    
)  # you might choose any port number > 1024
Mod('simplenode',  # the name of the module
    'frappy_Rachit.simple_node.SimpleNode',  # the class used for communication
    'SimpleNode',  # a description
    value= 1  # the serial connection
)    
    
