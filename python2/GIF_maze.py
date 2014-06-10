"""
GIF_maze.py

Generates mazes and creates an animated GIF of the process.

usage: GIF_maze.py [-h] [-size width height] [-thickness thickness]
               [-style algorithm] [-speed speed] [-fg R G B] [-bg R G B]
               [-alt R G B]
               file

positional arguments:
  file                  output file

optional arguments:
  -h, --help            show this help message and exit
  -size width height    size of the maze, in number of cells, e.g. 300x400
                        (default 100x100)
  -thickness thickness  the width (and height) of each cell in the maze
                        (default 1)
  -style algorithm      algorithm to use when generating the maze (default 1)
  -speed speed          the number of cells to draw per frame (default 10)
  -fg R G B             foreground color RGB values (default 200 200 200)
  -bg R G B             background color RGB values (default 10 10 10)
  -alt R G B            alternate foreground color RGB values (default 20 20 20)
"""

from struct import pack
import random, argparse

# LZW Constants
LZW_palette_bits = 2	# 2 bits (3 colors + transparent)
LZW_clear_code = 4
LZW_end_code = 5
LZW_max_codes = 4096

# Color indices
bg_index = 0
fg_index = 1
alt_fg_index = 2
trans_index = 3

# Classes				
   
class Bitmap:
	"""
	Bitmap represents a 2D grid of two-color pixels.
	The grid is divided into cells, where each cell is a square block of pixels,
	the size of which is determined by the constructor parameter *thickness*.
	
	Bitmap can encode the grid that it represents into an image data stream,
	suitable for inclusion in a GIF.
	Bitmap can also track changes made to itself and encode intermediate image
	data streams, making use of interframe transparency.
	"""
	
	def __init__ (self, width, height, thickness, track_changes = True):
		"""
		Create a new Bitmap.
		The parameters *width* and *height* determine the number of *thickness*
		size cells, so the total area of the grid (in pixels) is given by:
		(*width* x *thickness*) x (*height* x *thickness*)
		"""
		self.width = width
		self.height = height
		self.thickness = thickness
		self.data = [[0] * height * thickness for x in range(width * thickness)]
		self.changes = []
		self.diff_box = None
		self.track_changes = track_changes
			
	def encode_image (self, left, top, bg, fg):
		"""
		Encode the bitmap as an image descriptor block + LZW stream suitable for
		inclusion in a GIF image.
		"""
		
		# The initial code length is the number of bits used for the color table
		# plus one, to account for the clear and end codes
		code_length = LZW_palette_bits + 1
		# We start adding new codes immediately after the end code
		next_code = LZW_end_code + 1
		
		codes = {'0':bg, '1':fg}
		
		stream = DataBlock()
		stream.encode_bits(LZW_clear_code, code_length)
		pattern = str()
		for y in range(0, self.height * self.thickness):
				for x in range(0, self.width * self.thickness):
					pattern += str(self.data[x][y])
					if not codes.has_key(pattern):
						stream.encode_bits(codes[pattern[:-1]], code_length)
						codes[pattern] = next_code
						#TODO: think about optimizing this bit?
						if next_code == 2 ** code_length:
							code_length += 1
						next_code += 1
						if next_code == LZW_max_codes:
							next_code = LZW_end_code + 1
							stream.encode_bits(LZW_clear_code, code_length)
							code_length = LZW_palette_bits + 1
							codes = {'0':bg, '1':fg}
						pattern = pattern[-1]

		stream.encode_bits(codes[pattern], code_length)
		stream.encode_bits(LZW_end_code, code_length)
		
		descriptor = image_descriptor_block(left * self.thickness,
											top * self.thickness,
											self.width * self.thickness,
											self.height * self.thickness)
											
		return descriptor + stream.dump_bytes()
		
	def fill (self, x, y):
		"""
		Fill all pixels in the cell position (x, y).
		"""
		# In our topology, values that are too large or too small wrap around
		x %= self.width
		y %= self.height
		
		for ox in range(self.thickness):
			for oy in range(self.thickness):
				self.data[x*self.thickness + ox][y*self.thickness + oy] = 1
				
		# If we're tracking changes, add the filled cell to the list and expand 
		# the hitbox of changed cells accordingly
		if self.track_changes:		
			self.changes.append((x, y))
			if self.diff_box:
				left, top, right, bottom = self.diff_box
				if x < left:
					left = x
				elif x > right:
					right = x;
				if y < top:
					top = y;
				elif y > bottom:
					bottom = y;
				self.diff_box = (left, top, right, bottom)
			else:
				self.diff_box = (x, y, x, y)
		
	def get_diffmask (self):
		"""
		Return a semi-transparent GIF image segment that includes all the
		changes made to the bitmap since get_diffmask was last called.
		"""
		#TODO: perhaps this should behave better when not self.track_changes
		left, top, right, bottom = self.diff_box
		width = (right - left) + 1
		height = (bottom - top) + 1
		mask = Bitmap(width, height, self.thickness, track_changes = False)
		
		for x, y in self.changes:
			mask.fill(x - left, y - top)
				
		# clear changes
		self.changes = []
		self.diff_box = None
		return mask.encode_image(left, top, trans_index, fg_index)
		
	def get_connections (self, x, y):
		"""
		Return links between the cell (x, y) and empty cells near (x, y).
		Note that the cells returned are not directly adjacent to (x, y) but are
		spaced out by one cell.
		"""
		neighbors = [	(x, y, x + 2, y),
						(x, y, x - 2, y),
						(x, y, x, y + 2),
						(x, y, x, y - 2)]
		return [(x1, y1, x2, y2) for x1, y1, x2, y2 in neighbors if not self.test(x2, y2)]
	
	def num_changes (self):
		"""
		Return the number of changes made to the bitmap since get_diffmask was 
		last called.
		"""
		return len(self.changes)
			
	def test (self, x, y):
		"""
		Test whether the cell position (x, y) is filled.
		"""
		x %= self.width
		y %= self.height
		x *= self.thickness
		y *= self.thickness
		return self.data[x][y]


class DataBlock:
	"""
	DataBlock is a packed bitstream class, suitable for encoding the image data 
	blocks in a GIF image.
	"""
	
	def __init__ (self):
		"""
		Create a new DataBlock.
		"""
		self.bitstream = bytearray()
		self.pos = 0

	def encode_bits (self, num, size):
		"""
		Given a number *num* and a length in bits *size*, encode *num* as a 
		*size* length bitstring at the current position in the bitstream.
		"""
		string = bin(num)
		string = '0'*(size - len(string)) + string
		for digit in reversed(string):
			if len(self.bitstream) * 8 <= self.pos:
				self.bitstream.append(0)
			if digit == '1':
				self.bitstream[-1] |= 1 << self.pos % 8
			self.pos += 1

	def dump_bytes (self):
		"""
		Return a complete string representation of the image data block.
		An image data block consists of:
			a header byte (LZW_palette_bits),
			a number of data sub-blocks
			a terminator byte (0)
			
		Each sub-block is preceded by a byte indicating its length (0 to 255).		
		"""
		bytestream = ''
		while self.bitstream:
			if len(self.bitstream) > 255:
				bytestream += chr(255) + self.bitstream[:255]
				self.bitstream = self.bitstream[255:]
			else:
				bytestream += chr(len(self.bitstream)) + self.bitstream
				self.bitstream = bytearray()
		pos = 0
		return chr(LZW_palette_bits) + bytestream + chr(0)		


# Useful functions

def bin(s):
	"""
	Convert an integer into a binary string.
	Included for portability, Python 3 has this function built-in.
	"""
	return str(s) if s<=1 else bin(s>>1) + str(s&1)

def delay_frame (delay):
	"""Construct a spacer frame with no content that serves as a delay."""
	return (	graphics_control_block(delay) +
				image_descriptor_block(0, 0, 1, 1) +
				chr(LZW_palette_bits) +
				chr(1) +
				chr(trans_index) +
				chr(0) )
	
def loop_control_block ():
	"""Construct an application extension block that causes the GIF to loop.
	
	Format:
		extension header (1 byte, 0x21)
		extension label (1 byte, 0xFF)
		size of sub-block to follow (1 byte, 11)
		application identifier (8 bytes, 'NETSCAPE')
		application authentication code (3 bytes, '2.0')
		size of sub-block to follow (1 byte, 3)
		sub-block ID (1 byte, 1)
		loop count (1 byte, 0 indicates loop indefinitely)
		block terminator (1 byte, 0)
	"""
	return pack('<3B8s3s2BHB', 0x21, 0xFF, 11, 'NETSCAPE', '2.0', 3, 1, 0, 0)
	
def global_palette_block (bg, fg, mid):
	"""
	Construct the global palette block.  In simple RGB triples format.
	"""
	palette = bg + fg + mid + [0, 255, 0]
	return pack('12B', *palette);

def graphics_control_block (delay):
	"""
	Construct a graphics control block.
	Format:
		extension header (1 byte, 0x21)
		graphic control label (1 byte, 0xF9)
		size of sub-block to follow (1 byte, 4)
		packed byte
			bit(s)	explanation
			1-3		Reserved
			4-6		Disposal method
			7		User input flag
			8		Transparent color flag
		delay time (2 bytes)
		transparent color index (1 byte, always 3 in our case)
		block terminator (1 byte, 0)
	"""
	return pack("<4BH2B", 0x21, 0xF9, 4, 0b00000001, delay, trans_index, 0)

def image_descriptor_block (left, top, width, height):
	"""
	Construct an image descriptor block.
	Format:
		image separator (1 byte, 0x2C)
		image left (2 bytes)
		image top (2 bytes)
		image width (2 bytes)
		image height (2 bytes)
		packed byte
			bit(s)	explanation
			1		Local color table flag
			2		Interlace flag
			3		Sort flag
			4-5		Reserved
			6-8		# of bits in local color table - 1
	"""
	return pack('<B4HB', 0x2C, left, top, width, height, 0)	

def logical_screen_descriptor_block (height, width):
	"""
	Construct the logical screen descriptor block.
	Format:
		image width (2 bytes)
		image height (2 bytes)
		packed byte
			bit(s)	explanation
			1		Global color table flag
			2-4		Color resolution - 1 (see GIF standard)
			5		Sort flag (see GIF standard)
			6-8		# of bits in global color table - 1
		background color index (1 byte)
		pixel aspect ratio (1 byte)
	"""
	return pack('<2H3B', image_width, image_height, 0b10010001, 0,	0)

def validate_color (color):
	"""Check whether or not an RGB tuple is acceptable."""
	for val in color:
		if val < 0 or val > 255:
			return False
	return True

# Main program starts here

# Begin by parsing and validating the arguments

parser = argparse.ArgumentParser()
parser.add_argument('output', metavar='file', type=str, help='output file')
parser.add_argument('-size', metavar=('width', 'height'), type=int, nargs=2,
	help='size of the maze, in number of cells, e.g. 300x400 (default 100x100)')
parser.add_argument('-thickness', metavar='thickness', type=int,
	help='the width (and height) of each cell in the maze (default 1)')
parser.add_argument('-style', metavar='algorithm ', type=int,
	help='algorithm to use when generating the maze (default 1)')
parser.add_argument('-speed', metavar='speed', type=int,
	help='the number of cells to draw per frame (default 10)')
parser.add_argument('-fg', metavar=('R', 'G', 'B'), type=int, nargs=3,
	help='foreground color RGB values (default 200 200 200)')
parser.add_argument('-bg', metavar=('R', 'G', 'B'), type=int, nargs=3,
	help='background color RGB values (default 10 10 10)')
parser.add_argument('-alt', metavar=('R', 'G', 'B'), type=int, nargs=3,
	help='alternate foreground color RGB values (default 20 20 20)')
args = parser.parse_args()

width, height = args.size if args.size else (100,100)
if width < 2 or width % 2:
	print("Width must be positive and divisible by two, defaulting to 100")
	width = 100
if height < 2 or height % 2:
	print("Height must be positive and divisible by two, defaulting to 100")
	height = 100

thickness = args.thickness if args.thickness else 1
if thickness < 1:
	print("Thickness must be greater than one, defaulting to 1")
	thickness = 1
	
algorithm = args.style if args.style else 1
if algorithm not in [1, 2, 3]:
	print("Algorithm must be either 1, 2 or 3, defaulting to 1")
	algorithm = 1

cells_per_frame = args.speed if args.speed else 10
if cells_per_frame < 1:
	print("Drawing speed must be at least 1, defaulting to 10")
	cells_per_frame = 10
	
fg_color = args.fg if args.fg else [200, 200, 200]
if not validate_color(fg_color):
	print("All RGB values must be in the range 0-255")
	print("Defaulting foreground to (200, 200, 200)")
	fg_color = [200, 200, 200]

bg_color = args.bg if args.bg else [10, 10, 10]
if not validate_color(bg_color):
	print("All RGB values must be in the range 0-255")
	print("Defaulting background to (10, 10, 10)")
	fg_color = [10, 10, 10]

alt_color = args.alt if args.alt else [20, 20, 20]
if not validate_color(bg_color):
	print("All RGB values must be in the range 0-255")
	print("Defaulting alternate foreground to (20, 20, 20)")
	fg_color = [20, 20, 20]
	
# Initialize other variables
image_width = width * thickness
image_height = height * thickness

bitmap = Bitmap(width, height, thickness)

x = int(bitmap.width / 2)	# Start at roughly the center of the grid
y = int(bitmap.height / 2)

bitmap.fill(x, y)	# Fill the first cell

periphery = bitmap.get_connections(x, y)
random.shuffle(periphery)

stream = str()

# Construct the maze
# The maze is built by keeping track of possible ways to expand it and selecting
# one of them semi-randomly, depending on the chosen algorithm.
while periphery:
	if algorithm == 1:
		# Algorithm 1 selects only the most recent possible expansion added to 
		# the periphery.  Note that in this case, the possible expansions
		# associated with each new cell are shuffled randomly.
		# Algorithm 1 is something like a depth-first search.
		ox, oy, x, y = periphery.pop()
	elif algorithm == 2:
		# Algorithm 2 selects a possible expansion totally at random.
		# Algorithm 2 is something like a random search.
		pos = random.randint(0, len(periphery) - 1)
		ox, oy, x, y = periphery.pop(pos)
	else:
		# Algorithm 3 selects a possible expansion from a pool of those recently
		# added to the periphery - it's a cross between algorithms 1 & 2.
		# 30 is a magic number here, picked by hand
		pos = random.randint(max(0, len(periphery) - 30), len(periphery) - 1)
		ox, oy, x, y = periphery.pop(pos)

	# If the selected cell has already been filled, try again
	if bitmap.test(x, y):
		continue

	child = (x, y)
	connector = ((x + ox)/2, (y + oy)/2)
	
	bitmap.fill(*child)
	bitmap.fill(*connector)
	
	neighbors = bitmap.get_connections(x, y)
	
	if algorithm == 1:
		random.shuffle(neighbors)
	
	periphery += neighbors
	
	if bitmap.num_changes() >= cells_per_frame:
		stream += graphics_control_block(2) + bitmap.get_diffmask()

# If there are any unwritten changes, write them
if bitmap.num_changes() > 0:
	stream += graphics_control_block(2) + bitmap.get_diffmask()

# Prepend an alternate color version of the constructed maze to the stream and 
# add delay frames to the beginning and end
stream = (	bitmap.encode_image(0, 0, bg_index, alt_fg_index) +
			delay_frame(50) +
			stream +
			delay_frame(300) )

# Finally, build the header information and write everything to disk
image_descriptor = logical_screen_descriptor_block(image_width, image_height)

palette = global_palette_block(bg_color, fg_color, alt_color)

open(args.output, 'w').write('GIF89a' +			# GIF header
							image_descriptor + 
							palette + 
							loop_control_block() +
							stream +
							'\x3B')				# GIF footer