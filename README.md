mazes
=====

Animated GIF maze generator, in various languages.

This is a relatively simple program that generates mazes on a toroidal topology and writes the maze generation process out as an animated GIF file.  [Here's an example.](/examples/algorithm1-500x500.gif?raw=true)  It contains an implementation of the LZW algorithm for encoding the animated GIFs.  It'd be useful to study for anyone who is interested in the internals of the GIF standard, or who is interested in a simple way to generate mazes.

There are three possible maze generation algorithms that can be selected from the command line, using the -style option.

* Algorithm 1:
	Depth first seach like algorithm - runs until it reaches a dead end, then backtracks.  This generates very complex mazes and it's fun to watch it worm its way around the screen.
	
	[Algorithm 1 example.](/examples/algorithm1-thickness4-128x128.gif?raw=true)
	
* Algorithm 2:
	Random search algorithm - expands outward randomly.  Very slow compared to algorithm 1, largely because the chaotic nature of its expansion forces the GIF encoder to include large sections of the image for each frame.  This looks more like liquid spreading out on a surface.
	
	[Algorithm 2 example.](/examples/algorithm2-thickness4-128x128.gif?raw=true)
	
* Algorithm 3:
	Hybrid algorithm - this is a combination of the above two algorithms.  It's not quite as orderly as algorithm 1, but not as uniformly random as algorithm 2.  It has a very organic looking growth process.
	
	[Algorithm 3 example.](/examples/algorithm3-thickness4-128x128.gif?raw=true)
	

I am planning on implementing a version of this in each programming language I know, as a programming exercise.  Presently, Python (2.7 branch) is the only version that's finished.