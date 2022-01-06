"""Support for Lenovo bios update ISO files.
Given a .iso file, candidate capsule files are identified and extracted in memory on demand.
"""

from io import BytesIO
import os
import re

try:
	import eltorito as et
except ImportError:
	print('Can\'t import eltorito. Have you done `git submodule update --init`?')
	exit(1)
from FATtools import Volume
from kaitai.mbr_partition_table import MbrPartitionTable

BIOS_CAPSULE_EXTENSION = r'\.FL\d+' # Matching FL1/FL2/FL...
LBA_BLOCK_SIZE = 512 # Assumed for historic reasons

def file_applicable(file_path):
	return '.iso' in os.path.split(file_path)[-1] and os.path.isfile(file_path)

def filter_files(path_list):
	"""Given a list of paths, return the list of suitable files
	"""
	return [ f for f in path_list if file_applicable(f) ]


def _find_candidate_capsules(volume):
	"""Find efi capsule files in iso image by path such as
		/FLASH/<some subfolder name>/<some file name>.FL*
	Returns a list paths
	"""
	top_folder = 'FLASH'

	file_info = []
	subdirs = []
	for dir in volume.opendir(top_folder).iterator():
		if dir.IsDir():
			# Find all subfolder of <top_folder>
			subdirs.append(dir.Name()) # Don't care for longname, folder name is required only to access files in FAT partition

	for d in subdirs:
		if d in ['.', '..']:
			continue
		for file in volume.opendir( '/'.join( [top_folder, d] ) ).iterator():
			f_name = file.LongName() if file.IsLfn() else file.Name() # Might need longname for the extension
			if re.search(BIOS_CAPSULE_EXTENSION, f_name):
				file_info.append( '/'.join( [top_folder, d, f_name] ) )
	file_info.sort()
	return file_info

class LenovoISOCapsule(object):
	def __init__(self, volume_handle, capsule_path):
		self.volume_handle = volume_handle
		self.capsule_path = capsule_path

	def __enter__(self):
		self.capsule_handle = self.volume_handle.open(self.capsule_path)
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.capsule_handle.close()

	def read(self, size=-1):
		return bytes(self.capsule_handle.read(size)) # Cast to bytes to get read-only-like file

	def size(self):
		# Return filesize
		fopen = self.volume_handle.open(self.capsule_path)
		size = fopen.File.filesize
		fopen.close()
		return size

class FileParser(object):
	def __init__(self, iso_path):
		self.iso_path = iso_path

		if not os.path.isfile(self.iso_path):
			raise FileNotFoundError(f'Can\t open iso {self.iso_path}')

	def __enter__(self):
		self.iso_handle = open(self.iso_path, 'rb')

		# Get el torito image from iso
		extracted = et.extract(self.iso_handle)

		mbr = MbrPartitionTable.from_bytes(extracted['data'].getbuffer())

		if mbr.partitions[0].lba_start == 0 or any([ mbr.partitions[i].lba_start != 0 for i in range(1,len(mbr.partitions)) ]):
			# Only images with the first partition populated and all other partitions empty are supported
			raise ValueError('Received in input a disk image whith either the first partition empty or more partitions populated')

		part_start_offset = mbr.partitions[0].lba_start * LBA_BLOCK_SIZE
		# Assuming partition's end offset to correspond with file end, since there are no other partitions

		extracted['data'].seek(part_start_offset) # Move cursor beyond non-FAT data
		partition_buffer = BytesIO( extracted['data'].read() ) # Read to the end (no other partitions after this)
		self.volume = Volume.vopen(partition_buffer)

		paths = _find_candidate_capsules(self.volume)
		self.capsules = dict( [ [path.split('/')[-1], path] for path in paths ] ) # Associate filename to its full path

		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.iso_handle.close()

	def list_capsules(self):
		# Returns the list capsules (filenames) in currently opened iso
		return list(self.capsules)

	def open(self, capsule_name):
		if capsule_name not in self.capsules:
			raise KeyError(f'No available capsule with name {capsule_name} in iso {self.iso_path}')

		capsule_path = self.capsules[capsule_name]
		return LenovoISOCapsule(self.volume, capsule_path)
