FUN(K)
======
A tool for mechanically generating VHDL architectures which approximate differentiable functions. 

It outputs a piece-wise linear approximator implemented according to the _look and multiply_ method. 

The resulting module will support signed representation in a fixed point number format predefined by the user.  
A test bench is also generated, and will be used to compute the exhaustive response of the module.

The obtained design can be used in data-flow (one input per cycle), but the response delay is of 5 cycles.

This project has been FPGA proven on a Artix-200T @ 250Mhz

Author: B. Halimi (c) 2016 - Contact: <bhalimi@outlook.fr> - License: MIT

Dependencies
------------
- Python (2.7 or later) for running the script. ```[sudo apt-get install python2.7] ```
- GHDL, for analysis, elaboration and benchmarking the design. ```[download here : http://ghdl.free.fr/]```
- GNUPlot, for plotting the response of the architecture to the stimulation. ```[sudo apt-get install gnuplot]```

How to use
----------
The header of _generate.py_ must be configured. It asks for:

- the user function (ex: gaussian, logistic, inverse square-root ...)  

- the fixed point, signed, number format used, in Q representation (ex: Q8.8, Q2.6, ...)  

- the number of _retained bits_, that is to say the number of MSBs taken as is.  
A typical value would be the number of bits of the entire parts in the Q representation.  
The bigger it is, the larger are the ROMs, but the smaller is the multiplier.  
So you may wan't to play around with this value ;)
	 
Once configured, you just have to call ```python generate.py``` : this script build the VHDL project and it's test bench,  
then call a GHDL based simulation of the design, and finally, run GNUPlot which displays the simulation's results.
	 
Use case
--------
If you are crafting up an FPGA design and you want to use a non-linear function, this will probably do the job.

Nevertheless for very specific functions such as trigonometry, exponential, or polynoms, i would recommend to use dedicated techniques. In this case, you may want to take a look at CORDIC and LBST before using this project :) 

In other cases, enjoy !

