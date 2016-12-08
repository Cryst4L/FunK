import os, math, textwrap

#-Configuration-----------------------------------------------------------------
number_format = "Q8.12"	# fixed point precision
retained_msbs = 10		# number of msb to keep as is
def f(x): 				# function to interpolate
	return (math.exp(x) - math.exp(-x)) / (math.exp(x) + math.exp(-x))	

#-Generators--------------------------------------------------------------------
class Entity:
	"A VHDL entity generator"
	
	def __init__(self, name):
		self.port_list = []
		self.name = name

	def add_port(self, name, io, width):
		assert ((io in ('in', 'out', 'inout')) & (width >= 0)),"Invalid port declaration !"
		self.port_list.append((name, io, width))

	#def flush_port_list() ...

	def generate(self, dirpath):
		fo = open(dirpath + self.name + ".vhd", "wb")
		fo.write((
			"-- This file has been mechanically generated\n"
			"library ieee;\n"
			"use ieee.std_logic_1164.all;\n"
			"use ieee.numeric_std.all;\n\n"
			"entity %(name)s is\n"
			"	port(\n"
		) % {'name': self.name})

		for i, port in enumerate(self.port_list):
			logic_type = "std_logic" 
			if (port[2] > 1): logic_type += ("_vector(%d downto 0)" % (port[2]-1))
			if (i != len(self.port_list) - 1): logic_type += ";"
			fo.write("\t\t%s\t: %s %s\n" % (port[0], port[1], logic_type))

		fo.write("\t);\nend entity;\n\n")
		fo.close()
			
class LUT:
	"A VHDL look-up table generator"

	def __init__(self, name, width):
		self.name = name
		self.entity = Entity(name)
		self.width = width
		self.data = []

	def binarize(self, value, width):
		mask = int("1" * width, 2)
		return bin(int(value) & mask)[2:].zfill(width)

	def fill(self, data):
		self.data = data

	def generate(self, dirpath):
		# Generate the entity
		addr_width = int(math.ceil(math.log(len(self.data), 2)))
		self.entity.add_port('addr_i',  'in', addr_width)
		self.entity.add_port('data_o', 'out', self.width)
		self.entity.generate(dirpath)

		# Generate the achitecture
		fo = open(dirpath + self.name + ".vhd", "a")
		fo.write((
			"architecture procedural of %(name)s is\n"
			"begin\n"
			"	P_look_up : process(addr_i)\n"
			"	begin\n"
			"		case addr_i is\n"
		) % {'name': self.name})

		for i in range(0, len(self.data)):
			address = self.binarize(self.data[i][0], addr_width)
			value = self.binarize(self.data[i][1], self.width)
			fo.write("\t\t\twhen \"%s\" => data_o <= \"%s\";\n" % (address, value))

		# if ((2 ** addr_width) != len(self.data)):
		fo.write("\t\t\twhen others => data_o <= \"%0*d\";\n" % (self.width, 0))

		fo.write(
			"		end case;\n"
			"	end process;\n"
			"end architecture;\n"
		)

		fo.close()

#-Top level plain HDL-----------------------------------------------------------
top_level_inst = """
	I_offset_table: entity work.offset_table
	Port map (
		addr_i => msb_r,
		data_o => offset_s
	);

	I_slope_table: entity work.slope_table
	Port map (
		addr_i => msb_r,
		data_o => slope_s
	);
	"""

top_level_logic = """
	P_look_n_multiply : process(clk)
	begin
		if rising_edge(clk) then
		
			-- 1st register line
			msb_r <= msb_s;
			lsb_r <= lsb_s;

			-- 2nd register line
			lsb_b_r <= lsb_r;
			slope_r <= slope_s;
			offset_r <= offset_s;
			
			-- 3rd register line
			offset_b_r <= offset_r;
			product_s <= signed(slope_r) * signed("0" & lsb_b_r);

			-- 4th register line
			result_s <= signed(offset_b_r) + signed(product_s(%(h)d downto %(l)d)); 

		end if;
	end process;
	""" 

#-Build the sources ------------------------------------------------------------
def build_src():

	os.system("mkdir -p src")

	q_format = [ int(n) for n in number_format[1:].split(".") ]
	support = 2**(retained_msbs-1)

	#-Generate the look-up tables-----------------------------------------------
	offset_table = []
	for addr in range(-support, support):
		offset = f(2 ** (q_format[0] - retained_msbs) * addr) 
		offset *= (2 ** q_format[1])
		offset_table.append((addr, offset))
		
	offset_factory = LUT('offset_table', sum(q_format))
	offset_factory.fill(offset_table)
	offset_factory.generate("src/")

	slope_table = []
	for addr in range(-support, support-1):
		slope = f(2 ** (q_format[0] - retained_msbs) * (addr + 1))
		slope -= f(2 ** (q_format[0] - retained_msbs) * addr)
		slope *= (2 ** (q_format[1] - q_format[0] + retained_msbs))
		slope_table.append((addr, slope))
	
	slope_factory = LUT('slope_table', sum(q_format))
	slope_factory.fill(slope_table)
	slope_factory.generate("src/")
	
	print "# > ROMs' size : %d words" % (2* support)
	print "# > Multiplier size : %dx%d" % (sum(q_format), retained_msbs+1)


	#-Generate the top_level entity---------------------------------------------
	top_level = Entity('top_level')
	top_level.add_port('clk',  'in', 1)
	top_level.add_port('data_i',  'in', sum(q_format))
	top_level.add_port('data_o', 'out', sum(q_format))
	top_level.generate("src/")

	#-Generate the top_level achitecture----------------------------------------
	fo = open("src/top_level.vhd", "a")
	fo.write("architecture structural of top_level is\n\n")

	fo.write(
		(
			"\tsignal msb_s\t\t: std_logic_vector(%(b)d downto 0) := (others => '0');\n"
			"\tsignal msb_r\t\t: std_logic_vector(%(b)d downto 0) := (others => '0');\n\n"
		) % {'b' : retained_msbs-1} +
		(
			"\tsignal lsb_s\t\t: std_logic_vector(%(b)d downto 0) := (others => '0');\n"
			"\tsignal lsb_r\t\t: std_logic_vector(%(b)d downto 0) := (others => '0');\n"
			"\tsignal lsb_b_r\t\t: std_logic_vector(%(b)d downto 0) := (others => '0');\n\n"
		) % {'b' : sum(q_format)-retained_msbs-1} +
		(
			"\tsignal offset_s\t\t: std_logic_vector(%(b)d downto 0) := (others => '0');\n"
			"\tsignal offset_r\t\t: std_logic_vector(%(b)d downto 0) := (others => '0');\n"
			"\tsignal offset_b_r\t: std_logic_vector(%(b)d downto 0) := (others => '0');\n\n"
		) % {'b' : sum(q_format)-1} +
		(
			"\tsignal slope_s\t\t: std_logic_vector(%(b)d downto 0) := (others => '0');\n"
			"\tsignal slope_r\t\t: std_logic_vector(%(b)d downto 0) := (others => '0');\n\n"
		) % {'b' : sum(q_format)-1} +
		(
			"\tsignal product_s\t: signed(%(b)d downto 0) := (others => '0');\n\n"
		) % {'b' : 2*sum(q_format)-retained_msbs} +
		(
			"\tsignal result_s\t\t: signed(%(b)d downto 0) := (others => '0');\n"
			"\tsignal result_r\t\t: signed(%(b)d downto 0) := (others => '0');\n\n"
		) % {'b' : sum(q_format)-1}
	)

	fo.write("begin\n")

	fo.write(
		(	"\n\tmsb_s <= data_i(%d downto %d);"
		) % (sum(q_format)-1, sum(q_format)-retained_msbs) +
		(	"\n\tlsb_s <= data_i(%d downto 0);\n"
		) % (sum(q_format)-retained_msbs-1)
	)

	fo.write(top_level_inst)
	
	high = min(sum(q_format)+q_format[1]-1, 2*sum(q_format)-retained_msbs)

	fo.write(top_level_logic % {'h' : high, 'l' : q_format[1]})

	fo.write(
		(
			"\n\tdata_o <= std_logic_vector(result_s(%d downto 0));\n\n"
			"end architecture;\n"
		) % (sum(q_format)-1)
	)

	fo.close()

#-Test bench plain HDL----------------------------------------------------------
test_bench_head = """
	library ieee;
	use ieee.std_logic_1164.all;
	use ieee.numeric_std.all;
	use ieee.math_real.all;

	library std;
	use std.textio.all;
	"""

test_bench_lib = """
	constant clk_half_period : time := 50 ns;
	
	signal sim_input_s	: real := 0.0;
	signal sim_result_s	: real := 0.0;
	
	signal sim_done_s	: boolean := false;

	procedure Print(s : string) is 
		variable buf : line; 
		begin
			write(buf, s); 
			WriteLine(OUTPUT, buf); 
	end procedure Print;

	component top_level 
	port (
		clk : in std_logic;
		data_i : in std_logic_vector(%(b)d downto 0);
		data_o : out std_logic_vector(%(b)d downto 0)
	);
	end component;

	signal clk		: std_logic := '0';
	signal input_s	: std_logic_vector(%(b)d downto 0) := %(init_i)s;
	signal output_s	: std_logic_vector(%(b)d downto 0) := %(init_o)s;
	"""

test_bench_arch = """
	-- device under test
	I_dut: top_level  
	port map
	(
		clk => clk,
		data_i => input_s,
		data_o => output_s
	);
	
	-- clock process
	p_clk: process
	begin
		if (sim_done_s = true) then
			wait;
		else
			wait for clk_half_period;
			clk <= not clk; 
		end if;	
	end process;
	
	-- benchmark process
	p_bench: process
	begin
		wait for 5 us;
		l_stim: for it in 1 to %(it)d loop
			sim_input_s <= real(to_integer(signed(input_s))) / %(scaling)f;	
			sim_result_s <= real(to_integer(signed(output_s))) / %(scaling)f;
			
			input_s <= std_logic_vector(signed(input_s) + %(stride)d);
			wait for 1 us;
			
			Print(real'image(sim_input_s) & HT & real'image(sim_result_s));
		end loop;
		sim_done_s <= true;
		wait;
	end process;
	"""

#-Build the test bench ---------------------------------------------------------
def build_tb():

	q_format = [ int(n) for n in number_format[1:].split(".") ]

	os.system("mkdir -p tb")
	fo = open("tb/test_bench.vhd", "wb")

	fo.write(textwrap.dedent(test_bench_head));

	fo.write("entity test_bench is\nend;\n\n")

	fo.write("architecture structural of test_bench is\n")

	init_i = "\"1" + "0" * (sum(q_format)-1) + "\""
	init_o = "(others => '0')" 

	fo.write(test_bench_lib % {'b' : sum(q_format)-1, 'init_i' : init_i, 'init_o' : init_o})

	fo.write("\nbegin\n");

	scaling = 2 ** q_format[1]
	
	linear_range = sum(q_format)-retained_msbs;
	stride = int(2 ** (sum(q_format)-retained_msbs-4)) if linear_range > 3 else 1
	iteration = (2 ** sum(q_format)) / stride

	fo.write(test_bench_arch % {'it' : iteration, 'scaling' : scaling, 'stride': stride})

	fo.write("\nend architecture;\n")

	fo.close()
	
#-Script body ------------------------------------------------------------------
def main():

	#-Generate the HDL project--------------------------------------------------
	print "# Generating the sources files ..."
	build_src()
	print "# Generating the test bench ..."
	build_tb()

	#-Run the GHDL simulator----------------------------------------------------
	print "# Elaborating the design (GHDL) ..."
	os.system("mkdir -p simu")
	os.system("ghdl -a --workdir=simu --work=work src/*.vhd tb/*.vhd")
	os.system("ghdl -e --workdir=simu --work=work test_bench")
	
	print "# Benchmarking the design (GHDL) ..."
	os.system("./test_bench > out.dat")
	os.system("rm -rf simu *.o")
	
	#-Display the simulation results--------------------------------------------
	print "# Displaying the benchmark results ..."
	os.system("gnuplot draw.p -persist")
	
	
	
#-Call the main ----------------------------------------------------------------
if __name__ == "__main__":
    main()
