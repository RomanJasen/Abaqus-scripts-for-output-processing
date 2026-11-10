# -*- coding: utf-8 -*-
"""
Material_CDP_ECformula_to_tuple_preparation.py - reads the parameters of CDP materials
(concrete damaged plasticity) that are generated with the Eurocode formula
(Material_CDP_ECformula_to_tuple.py).

INPUT: text files (*.txt) in the folder A_Material_input_indirect next to this script,
one material per line, tab separated (a leading tab is allowed):
    name   E   v   s_max   e_smax   e_u   (not used)   Sigma_T   GFI
    E      modulus of elasticity             s_max   compressive strength
    v      Poisson's ratio                   e_smax  strain at s_max     e_u  ultimate strain
    Sigma_T  tensile strength                GFI     tensile fracture energy
Empty lines and lines starting with # are ignored.

Run on its own (python or abaqus python) to list the materials found.
"""
from __future__ import print_function

import os

INPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "A_Material_input_indirect")


def dict_creation(lines):
    """{material name: {"E", "v", "s_max", "e_smax", "e_u", "Sigma_T", "GFI"}} of the lines of one file."""
    result_dict = {}
    for line in lines:
        if not line.strip() or line.strip().startswith("#"):
            continue
        values = [v for v in line.strip("\n").split("\t") if v.strip()]
        result_dict[values[0].strip()] = {
            "E": float(values[1]), "v": float(values[2]), "s_max": float(values[3]),
            "e_smax": float(values[4]), "e_u": float(values[5]),
            "Sigma_T": float(values[7]), "GFI": float(values[8])}
    return result_dict


def Generate_material_dictionaries(folder=INPUT_FOLDER):
    """Materials of all *.txt files in the input folder ({} if the folder does not exist)."""
    total = {}
    if not os.path.isdir(folder):
        return total
    for file_name in sorted(os.listdir(folder)):
        if file_name.lower().endswith(".txt"):
            with open(os.path.join(folder, file_name), "r") as f:
                total.update(dict_creation(f.readlines()))
    return total


if __name__ == "__main__":
    materials = Generate_material_dictionaries()
    print("%d material(s) in %s" % (len(materials), INPUT_FOLDER))
    for name in sorted(materials):
        print("  %-20s %s" % (name, materials[name]))
