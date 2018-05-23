from optimizer import optimize_comprehensions
import numpy as np
import matplotlib.pyplot as plt
import timeit
from functools import partial
from time import sleep
import random
from expensive_functions import *


def list_comprehension(expensive_func,a,**kargs):
    return [
        expensive_func(x,**kargs)
        for x in [a]
        if expensive_func(x,**kargs)
    ]

@optimize_comprehensions
def list_comprehension__optimized(expensive_func,a,**kargs):
    return [
        expensive_func(x,**kargs)
        for x in [a]
        if expensive_func(x,**kargs)
    ]
func_times = [x for x in range(900, 1000)]

opt_time =[]
cmp_time = []


expensive_func = function_two

for i in func_times:
    seed = random.random()*10000
    print("I= ", i,"seed = " ,seed)
    print("Running Non Optimized")
    comp_time = timeit.timeit( partial(list_comprehension, expensive_func, i,seed=seed), number=5)
    cmp_time.append(comp_time)
    print("Running Optimized")
    optimized_comp_time = timeit.timeit(partial(list_comprehension__optimized, expensive_func,i,seed=seed),number=5)
    opt_time.append(optimized_comp_time)

    print("Optimized = ", optimized_comp_time , "Non opti = ", comp_time,"\n")

with plt.rc_context({'axes.edgecolor':'gray', 'xtick.color':'gray', 'ytick.color':'gray', 'figure.facecolor':'white'}):

    plt.plot(func_times, opt_time, color='r')
    plt.plot(func_times, cmp_time,color='y')

    plt.ylabel('Execution time of optimized Time and original Time',  fontsize=10, wrap=True)
    plt.xlabel('Execution time of function (seconds)', fontsize=10)
    plt.savefig('Blah.svg')