#! /bin/python3

import argparse
import os
from types import ModuleType
from typing import Union

import uefi_firmware

import extractors.lenovo_exe as lenovo_exe
import extractors.lenovo_iso as lenovo_iso

# When adding further parsers:
#	1) Update parsers dictionary below
#	2) Update type hints in installers loop
parsers = {
	'lenovo_iso': lenovo_iso,
	'lenovo_exe': lenovo_exe,
}

argparser = argparse.ArgumentParser(
	description='Extract modules with given GUIDs from bios updaters'
)
argparser.add_argument(
	'path',
	help='the file/directory to work on. If a directory is passed, all the suitable files in that directory will be analyzed')
argparser.add_argument(
	'parser', choices=list(parsers),
	help='specify format of the given input files'
)
argparser.add_argument(
	'GUID', type=str, nargs='+',
	help='GUID(s) of the element(s) to extract'
)
argparser.add_argument(
	'-o', '--out-dir', type=str, default='out',
	help='name of the folder where output PE files will be stored (default: `out`)'
)
argparser.add_argument(
	'-f', '--force', action='store_true', default=False,
	help='overwrite output file(s)'
)
args = argparser.parse_args()

parser: ModuleType = parsers[args.parser]

# Finds only FirmwareFile objects, not FirmwareFileSystemSection
# Returns a list of tuples with the guid of the element and the element itself
def find_file_by_guid(firmware_tree, guids):
	def find_file_by_guid_core(firmware_tree, guids):
		r = []
		for obj in firmware_tree.iterate_objects():
			if obj.get('type', '') == 'FirmwareFile' and obj.get('guid', '') in guids:
				r.append( (obj.get('guid', ''), obj['_self']) )
			r.extend(find_file_by_guid_core(obj['_self'], guids))
		return r

	guids = [ guid.lower() for guid in guids ] # Force lowercase
	return find_file_by_guid_core(firmware_tree, guids)

# Extract all PE32 objects in a tree
def find_PE32(firmware_tree):
	if firmware_tree.attrs.get('type') == 16: # equals to get('type_name', '') == 'PE32 image'
		return [firmware_tree]
	else:
		r = []
		for obj in firmware_tree.iterate_objects():
			r.extend(find_PE32(obj['_self']))
		return r

# Accepts the content of a UEFI file as a bytes object and a list of GUIDs to identify in the object
# Returns a dictionary where a GUID (if found) is associated to its PE
def find_PEs(file_content, guids):
	uefi_parser = uefi_firmware.AutoParser(file_content)
	if uefi_parser.type() == 'unknown':
		raise NotImplementedError(f'[!] Unknown parser type')

	firmware = uefi_parser.parse()
	found_files = find_file_by_guid(firmware, guids)

	if len(found_files) == 0:
		raise FileNotFoundError()

	pes = {}
	for guid, file in found_files:
		if guid not in pes:
			pes[guid] = []
		pes[guid].extend(find_PE32(file))
	return pes

def gen_filename(dest_folder, installer_path, capsule_path, guid):
	_, installer_filename = os.path.split(installer_path)
	_, capsule_filename = os.path.split(capsule_path)
	return os.path.join(dest_folder, f'{installer_filename}_{capsule_filename}_{guid}')

def write_file(installer_path, capsule_name, guid, data):
	dest_path = gen_filename(args.out_dir, installer_path, capsule_name, guid)

	if os.path.exists(dest_path):
		overwrite = None
		while overwrite not in ['y', 'n', '']:
			overwrite = input(f'[?] File {dest_path} exists already. Overwrite [y/N]? ').lower()
		if overwrite in ['n', '']:
			print(f'[*] File {dest_path} skipped')
			return

	with open(gen_filename(args.out_dir, installer_path, capsule_name, guid), 'wb') as pe_out:
		pe_out.write(data)


# Prepare output directory
args.out_dir = os.path.join(os.getcwd(), args.out_dir)
if not os.path.exists(args.out_dir):
	os.makedirs(args.out_dir, exist_ok=True)

# Detect if args.path is a single executable or a folder. If folder, find list of all exe file within it
installers = []
if os.path.isdir(args.path):
	# Filter all suitable files in passed directory
	installers = parser.filter_files( [ os.path.join(args.path, f) for f in os.listdir(args.path) ] )
else:
	if not os.path.exists(args.path):
		raise FileNotFoundError(f'File {args.path} does not exist')
	elif not parser.file_applicable(args.path):
		raise TypeError(f'File {args.path} is not suitable for {args.parser}')
	installers = [args.path]

for installer_path in installers:
	with parser.FileParser(installer_path) as f:
		f: Union[lenovo_iso.FileParser, lenovo_exe.FileParser]

		for caps in f.list_capsules():
			with f.open(caps) as c:
				try:
					pes = find_PEs(c.read(), args.GUID)
				except FileNotFoundError:
					print(f'[!] Did not find any matching GUID in {caps}')
					continue
				except NotImplementedError:
					print(f'[!] Unknown filetype for {caps}, skipping')
					continue

				for guid in pes:
					for pe in pes[guid]:
						write_file(installer_path, caps, guid, pe.data)
