# -*- coding: utf-8 -*-
"""
Material_CDP_direct_to_tuple.py - reads CDP materials (concrete damaged plasticity) whose
tables are given directly, e.g. calibrated in a spreadsheet and pasted as text.

INPUT: one material per *.txt file in the folder A_material_input_direct next to this
script (the file name is the material name), tab separated, laid out like
A_material_input_direct/Example_direct.txt:
    E <tab> value                          row 1
    v <tab> value                          row 2
    (2 empty rows), C                      rows 3-5
    stress  inel def  Damage C  inel def  Plast_def      row 6, then one row per point
    (4 empty rows)
    Stress  GFI  Umax                      header, then one row: tensile strength, GFI, Umax
    (4 empty rows)
    Displ  Stress  DI  inel strain         header, then 3 rows of tension damage (DI, displacement)
The layout is checked (ValueError if a heading is not where it is expected).

Run on its own (python, with matplotlib) to plot the compression curves of all materials.
"""
from __future__ import print_function

import os

INPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "A_material_input_direct")


def dict_creation_manual_inputs(lines):
    """Tables of one material: {"Compression_input", "damageC", "tension_input", "damageT", "Elastic"}."""
    Content_matrix = []
    for line in lines:
        Content_matrix.append([v for v in line.strip("\n").split("\t") if v != ""])

    End_of_compression_data = 0
    for i, row in enumerate(Content_matrix):
        if "Stress" in row and "GFI" in row:
            if End_of_compression_data != 0:
                raise ValueError("'Stress' and 'GFI' were found twice in the material input")
            End_of_compression_data = i

    Check_dict = {(0, 0): "E", (1, 0): "v", (5, 0): "stress", (5, 1): "inel def", (5, 2): "Damage C",
                  (5, 3): "inel def", (5, 4): "Plast_def",
                  (End_of_compression_data, 0): "Stress", (End_of_compression_data, 1): "GFI",
                  (End_of_compression_data, 2): "Umax",
                  (End_of_compression_data + 5, 0): "Displ", (End_of_compression_data + 5, 1): "Stress",
                  (End_of_compression_data + 5, 2): "DI", (End_of_compression_data + 5, 3): "inel strain"}
    for (r, c), expected in Check_dict.items():
        try:
            found = Content_matrix[r][c]
        except IndexError:
            found = None
        if found != expected:
            raise ValueError("Material input: row %d column %d should be %r, found %r" % (r + 1, c + 1, expected, found))

    Elastic_input = tuple([(float(Content_matrix[0][1]), float(Content_matrix[1][1]))])
    Compressive_input, Damage_C = [], []
    for i in range(6, End_of_compression_data - 4):
        Compressive_input.append((float(Content_matrix[i][0]), float(Content_matrix[i][1])))
        Damage_C.append((float(Content_matrix[i][2]), float(Content_matrix[i][3])))
    Tension_input = tuple([(float(Content_matrix[End_of_compression_data + 1][0]),
                            float(Content_matrix[End_of_compression_data + 1][1]))])
    Damage_T = []
    for i in range(End_of_compression_data + 6, End_of_compression_data + 9):
        Damage_T.append((float(Content_matrix[i][2]), float(Content_matrix[i][3])))   # DI, displacement
    return {"Compression_input": Compressive_input, "damageC": Damage_C, "tension_input": Tension_input,
            "damageT": tuple(Damage_T), "Elastic": Elastic_input}


def Generate_material_dictionaries_DIRECT(folder=INPUT_FOLDER):
    """{material name (= file name): tables} of all *.txt files ({} if the folder does not exist)."""
    total = {}
    if not os.path.isdir(folder):
        return total
    for file_name in sorted(os.listdir(folder)):
        if file_name.lower().endswith(".txt"):
            with open(os.path.join(folder, file_name), "r") as f:
                total[os.path.splitext(file_name)[0]] = dict_creation_manual_inputs(f.readlines())
            print("read material file:", file_name)
    return total


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    materials = Generate_material_dictionaries_DIRECT()
    plt.figure(figsize=(10, 6))
    for name, tables in sorted(materials.items()):
        E = tables["Elastic"][0][0]
        eps0 = tables["Compression_input"][0][0] / E
        curve = [(0.0, 0.0)] + [(eps0 + inel, stress) for stress, inel in tables["Compression_input"]]
        plt.plot([p[0] for p in curve], [p[1] for p in curve], label=name)
    plt.xlabel("strain")
    plt.ylabel("compressive stress")
    plt.title("CDP compression curves (A_material_input_direct)")
    plt.legend()
    plt.show()
