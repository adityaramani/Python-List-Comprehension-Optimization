import numpy as np

a = 6

def create_matrix(n,seed):
    A = []
    for i in range(n):
        temp = []
        for j in range(n):
            temp.append(i+j+seed)
        A.append(temp)

    return np.array(A)
    
def function_one(x,**kargs):
    total = 0
    for i in range(x):
        total += i**i
    
    return total%2

def function_two(x,**kargs):
    if kargs['seed'] == None:
        seed = 1
    else:
        seed = kargs['seed']
    A = create_matrix(x,seed)
    B = create_matrix(x,seed)
    
    np.matmul(A,B)
    return 1

def function_three(x, **kargs):
    return 1

def function_impure(x, **kargs):
    global a
    a =a +  1
    print(a)
    return x+a

