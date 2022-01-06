"""Support for Lenovo Inno Installer bios update executable files.
Given a .exe file, candidate capsule files are identified and extracted in os's temp directory.
Temporary files are deleted when resources are freed
"""

import os
import re
import shutil
import subprocess
import tempfile

BIOS_CAPSULE_EXTENSION = r'\.FL\d+' # Matching FL1/FL2/FL...

def file_applicable(file_path):
	return '.exe' in os.path.split(file_path)[-1] and os.path.isfile(file_path)

def filter_files(path_list):
	"""Given a list of paths, return the list of suitable files
	"""
	return [ f for f in path_list if file_applicable(f) ]

# Find candidate UEFI capsule files in inno installer executable
# Returns a list of paths
def _find_candidate_capsules(filename):
	command = f'innoextract -l {filename}'.split()
	inno_list_result = subprocess.run(command, stdout=subprocess.PIPE)
	if inno_list_result.returncode != 0:
		raise RuntimeError(f'Got return code {inno_list_result.returncode} while listing files in inno istaller {filename}')
	paths = []
	for line in inno_list_result.stdout.decode('utf-8').split('\n'):
		if re.search(BIOS_CAPSULE_EXTENSION, line):
			line_split = line.split()
			paths.append(line_split[1][1:-1])
	return paths

# Extract one file (identified by internal archive path) from inno installer executable (identified by OS path)
# to a given directory (identified by OS path), created if not existing.
# Returns the full path of the extracted file
def _extract_capsule(filename, capsule_path, capsule_out_dir):
	command = f'innoextract --output-dir {capsule_out_dir} -I {capsule_path} {filename}'.split()
	inno_extract_result = subprocess.run(command, stdout=subprocess.PIPE)
	if inno_extract_result.returncode != 0:
		raise RuntimeError(f'Got return code {inno_extract_result.returncode} while extracting file {capsule_path} from inno istaller {filename}')
	return os.path.join(capsule_out_dir, capsule_path)

class LenovoExeCapsule(object):
	def __init__(self, exe_path, capsule_path, tempdir):
		self.exe_path = exe_path
		self.capsule_path = capsule_path
		self.tempdir = tempdir

	def __enter__(self):
		extracted_capsule_path = _extract_capsule(self.exe_path, self.capsule_path, self.tempdir.name)
		self.capsule_handle = open(extracted_capsule_path, 'rb')
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.capsule_handle.close()

	def read(self, size=-1):
		return self.capsule_handle.read(size)

	def size(self):
		# Return filesize
		self.capsule_handle.seek(0,2)
		size = self.capsule_handle.tell()
		self.capsule_handle.seek(0)
		return size

class FileParser(object):
	def __init__(self, exe_path):
		self.exe_path = exe_path
		self.tempdir = tempfile.TemporaryDirectory(prefix='uefiextract_', ignore_cleanup_errors=True)

		if not os.path.isfile(self.exe_path):
			raise FileNotFoundError(f'Can\t open installer exe {self.exe_path}')

		if shutil.which('innoextract') == None:
			raise RuntimeError('`innoextract` can\'t be found in PATH')

	def __enter__(self):
		paths = _find_candidate_capsules(self.exe_path)
		self.capsules = dict( [ (path.split('/')[-1], path) for path in paths ] ) # Associate filename to its full path
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.tempdir.cleanup()

	def list_capsules(self):
		# Returns the list capsules (filenames) in currently opened installer
		return list(self.capsules)

	def open(self, capsule_name):
		if capsule_name not in self.capsules:
			raise KeyError(f'No available capsule with name {capsule_name} in installer {self.exe_path}')

		capsule_path = self.capsules[capsule_name]
		return LenovoExeCapsule(self.exe_path, capsule_path, self.tempdir)
