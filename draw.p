#!/usr/bin/gnuplot
# Legends
set xlabel 'input'
set ylabel 'output'
set title "Response of the GHDL stimulation of the design"
# Config
set grid
set key inside bottom right
# Plot
plot "out.dat" using 1:2 with lines title 'y = f(x)'

