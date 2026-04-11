"""A deliberately bad Python file with many issues."""

import os, sys, json
import os
from os import *

unused_import = True

def process(data):
    try:
        result = eval(data)
    except:
        pass
    os.system("rm -rf /tmp/cache")
    x=1+2
    if x == True:
        print (x)
    return result

class bad:
    def Method(self):
        exec("print('hello')")
        l = []
        l = l
        return None
