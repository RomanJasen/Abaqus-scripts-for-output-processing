# -*- coding: utf-8 -*-
"""
Material_CDP_ECformula_to_tuple.py - turns material parameters into the tables of an
Abaqus CDP material (concrete damaged plasticity), with the compression curve of the
Eurocode formula  sigma = s_max (k n - n^2) / (1 + (k - 2) n),  n = eps / e_smax,
k = 1.05 E e_smax / s_max, and a linear tension softening.

    CDP_material_definition_ECformula({name: {"E", "v", "s_max", "e_smax", "e_u", "Sigma_T", "GFI"}})
    -> {name: {"Elastic", "Compression_input", "damageC", "tension_input", "damageT"}}
The tables are tuples ready for  ....setValues(table=...)  (see change_material in run_jobs.py).

Run on its own (python or abaqus python) for a test material.
"""
from __future__ import print_function


def CDP_material_definition_ECformula(Dict_of_material_params):
    Dict_of_completed_inputs = {}
    for key in Dict_of_material_params.keys():
        print("converting material:", key)
        material = Dict_of_material_params[key]

        # strains of the compression backbone curve: 20 equal steps up to e_u, plus e_smax
        List_of_def = [i * material["e_u"] / 20 for i in range(21)]
        if material["e_smax"] not in List_of_def:
            List_of_def.append(material["e_smax"])
            List_of_def.sort()

        List_of_sigma = []
        List_of_elastic_epsilon = []
        List_of_inelastic_epsilon = []   # input of Abaqus
        List_of_plastic_epsilon = []     # check only
        List_of_damage_param = []

        e1, E, s_u = material["e_smax"], material["E"], material["s_max"]
        for epsilon in List_of_def:
            n = epsilon / e1
            k = 1.05 * E * e1 / s_u
            sigma = s_u * (k * n - n * n) / (1 + (k - 2) * n)
            List_of_sigma.append(sigma)
            dam_par = 1 - sigma / s_u if epsilon > e1 else 0
            e_def = sigma / E
            List_of_elastic_epsilon.append(e_def)
            in_def = epsilon - e_def
            List_of_inelastic_epsilon.append(in_def)
            pl_def = in_def - (sigma * dam_par / (1 - dam_par)) / E if dam_par != 1.0 else in_def
            List_of_plastic_epsilon.append(pl_def)
            List_of_damage_param.append(dam_par)

        if any(i < 0 for i in List_of_plastic_epsilon):
            print("##################################")
            print("input parameters: E %s, v %s, s_max %s, e_smax %s, e_u %s, Sigma_T %s, GFI %s" % (
                E, material["v"], s_u, e1, material["e_u"], material["Sigma_T"], material["GFI"]))
            print("e_pl, e_in, e_el, stress")
            for i, value in enumerate(List_of_plastic_epsilon):
                print(value, List_of_inelastic_epsilon[i], List_of_elastic_epsilon[i], List_of_sigma[i])
            raise ValueError("plastic deformation (printed above) smaller than zero was found in %s" % key)

        starting_i = 0
        for i, eps in enumerate(List_of_inelastic_epsilon[:-1]):
            if eps == 0.0 and List_of_inelastic_epsilon[i + 1] > 0:
                starting_i = i

        Elastic_input = tuple([(material["E"], material["v"])])

        C_sigma_inel_eps_input = []
        Damage_C_input = []
        for i in range(starting_i, len(List_of_def)):
            if List_of_sigma[i] == 0 and List_of_inelastic_epsilon[i] == 0:
                C_sigma_inel_eps_input.append((0.2 * s_u, List_of_inelastic_epsilon[i]))
            else:
                C_sigma_inel_eps_input.append((List_of_sigma[i], List_of_inelastic_epsilon[i]))
            Damage_C_input.append((List_of_damage_param[i], List_of_inelastic_epsilon[i]))

        # tension: linear softening to zero at U_max = 2 GFI / Sigma_T
        Tension_input = tuple([(material["Sigma_T"], material["GFI"])])
        Damage_T_input = []
        U_max = 2 / material["Sigma_T"] * material["GFI"]
        for i in range(10):
            displ = U_max * (i / 10.0) if i > 0 else 0
            stress = material["Sigma_T"] * (1 - i / 10.0)
            Damage_T_input.append((1 - stress / material["Sigma_T"], displ))

        Dict_of_completed_inputs[key] = {"Compression_input": tuple(C_sigma_inel_eps_input),
                                         "damageC": tuple(Damage_C_input),
                                         "tension_input": Tension_input,
                                         "damageT": tuple(Damage_T_input),
                                         "Elastic": Elastic_input}
    return Dict_of_completed_inputs


if __name__ == "__main__":
    test = {"Test_mat": {"E": 40000, "v": 0.3, "s_max": 20, "e_smax": 0.002, "e_u": 0.0035, "Sigma_T": 2,
                         "GFI": 0.18}}
    for name, tables in CDP_material_definition_ECformula(test).items():
        print("MATERIAL:", name)
        for table_name, rows in tables.items():
            print("\n" + table_name)
            for row in rows:
                print("   ", row)
