# UEFI PE extractor
Extract one or more PEs from UEFI update isos/exe installers, given the GUIDs.

## Rationale
This project was born to quickly check for changes in the PE identified by the same GUID in different UEFI firmware versions. All the PEs with the given GUIDs will be extracted from every bios to the specified output folder.

## Dependencies
Depends on python module `uefi_firmware`. Also, `innoextract` must be in path to work with Lenovo exe installers.

```sh
git clone https://github.com/ceres-c/UEFI-extractor.git
cd UEFI-extractor
git submodule update --init
```

## Usage

```
./uefi-extract-all.py -h
usage: uefi-extract.py [-h] [-o OUT_DIR] [-f] path {lenovo_iso,lenovo_exe} GUID [GUID ...]

Extract modules with given GUIDs from bios updaters

positional arguments:
  path                  the file/directory to work on. If a directory is passed, all the suitable files in that directory will be analyzed
  {lenovo_iso,lenovo_exe}
                        specify format of the given input files
  GUID                  GUID(s) of the element(s) to extract

options:
  -h, --help            show this help message and exit
  -o OUT_DIR, --out-dir OUT_DIR
                        name of the folder where output PE files will be stored (default: `out`)
  -f, --force           overwrite output file(s)
```

## Supported vendors
Currently only Lenovo update files (both exe and iso) are supported. The architecture allows for easy extension of the project writing appropriate parsers for different vendors.
