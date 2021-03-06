# data/static/emission-factors.json is initially generated from this script.
# To update the file, run this script and copy the output, auto-emission-factors.json, to data/static/emission-factors.json.
# Be careful to keep changes that have been made to data/static/emission-factors.json if they're still relevant.
# NB: the pre-commit hooks format the file further. If you would like to see the changes before committing, run `pre-commit run`
#     on the staged emission-factors.json file.

import requests
import json
import csv


def ƒetch_emissions():
    r = requests.get(
        "https://data.ademe.fr/data-fair/api/v1/datasets/base-carbone(r)/lines?format=json&q_mode=simple&Type_Ligne_in=Poste&Type_de_l'%C3%A9l%C3%A9ment_in=Facteur%20d'%C3%A9mission&Statut_de_l'%C3%A9l%C3%A9ment_in=Valide%20g%C3%A9n%C3%A9rique%2CValide%20sp%C3%A9cifique&Type_poste_in=Combustion&sampling=neighbors&size=700"
    )
    body = r.json()
    results = body["results"]

    if body["total"] > len(results):
        raise Exception(
            f"There are {body['total']} emissions but only {len(results)} fetched, please revise script/query to get all results"
        )
    return results


def read_emissions_file(filename):
    with open(filename, "r", encoding="utf8") as csvfile:
        csvreader = csv.reader(csvfile, delimiter=",")
        headers = next(csvreader)
        for idx, header in enumerate(headers):
            headers[idx] = header.replace(" ", "_")
        results = []
        for row in csvreader:
            result = {}
            for idx, column in enumerate(row):
                result[headers[idx]] = column
            results.append(result)
        return results


# TODO: Ideal clean up actions
# - normalise units so don't have kWhPCI, kWh PCI and kWh (PCI) as separate units for example
def create_emission_factors_file(results):
    factors = {}
    duplicate_fe_by_unit = {}
    duplicate_count = 0
    posts = {}
    missing_post = []
    post_used = []
    total_efs_saved = 0
    ignored = 0

    with open("./files/posts.json", "r", encoding="utf8") as jsonfile:
        posts = json.load(jsonfile)

    for emission in results:
        # Dès la spécification :
        # "NB sur les FE : si un FE France et Europe existent pour le même combustible,
        # prendre le FE France uniquement.
        location = emission["Localisation_géographique"]
        if location == "Europe":
            ignored += 1
            continue

        emission_type = emission["Nom_base_français"]
        attribute = emission["Nom_attribut_français"]
        border = emission["Nom_frontière_français"]
        name_with_attribute = f"{emission_type}, {attribute}" if attribute else emission_type
        emission_key = f"{name_with_attribute}, {border}" if border else name_with_attribute

        unit = emission["Unité_français"]

        if emission_key not in factors:
            additional_info = get_additional_info(posts, emission, post_used, missing_post)
            factors[emission_key] = {
                "facteurs": {},
                "type": emission_type,
                "attribut": attribute,
                "frontière": border,
                "poste": additional_info["poste"] if additional_info else None,
                "groupe": additional_info["groupe"] if additional_info else None,
                "classification": additional_info["classification"]
                if additional_info and "classification" in additional_info
                else None,
            }

        location = get_location(emission)
        if location not in factors[emission_key]["facteurs"]:
            factors[emission_key]["facteurs"][location] = {}

        # note if there is a duplicate unit for emission type
        if unit in factors[emission_key]["facteurs"][location]:
            if emission_key not in duplicate_fe_by_unit:
                duplicate_fe_by_unit[emission_key] = {}
            duplicate_fe_by_unit[emission_key][unit] = duplicate_fe_by_unit[emission_key].get(unit, 0) + 1
            duplicate_count += 1
            continue

        # add to factors
        emission_factor = emission["Total_poste_non_décomposé"].replace(",", ".")
        if unit not in factors[emission_key]["facteurs"][location]:
            factors[emission_key]["facteurs"][location][unit] = emission_factor
            total_efs_saved += 1

    add_display_name(factors)

    with open("auto-emission-factors.json", "w", encoding="utf8") as jsonfile:
        json.dump(factors, jsonfile, indent=2, ensure_ascii=False)

    print(duplicate_fe_by_unit)
    print(f"Total ignored: {ignored}")
    print(f"Total duplicates: {duplicate_count}")
    print(f"Missing posts: {missing_post}")
    unused_posts = [name for name in posts.keys() if name not in post_used]
    print(f"Unused posts: {unused_posts}")
    print(f"Total efs saved: {total_efs_saved}")
    print(f"Total types: {len(factors.keys())}")
    return factors


def get_additional_info(posts, emission, post_used, missing_post):
    name = emission["Nom_base_français"]
    attribute = emission["Nom_attribut_français"]
    name_for_post = f"{name}, {attribute}" if attribute else name

    if name_for_post in posts:
        post_used.append(name_for_post)
        return posts[name_for_post]
    elif name in posts:
        post_used.append(name)
        return posts[name]
    missing_post.append(name_for_post)
    return None


def get_location(emission):
    location = emission["Localisation_géographique"]
    sub_location = emission["Sous-localisation_géographique_français"]
    if location == "Outre-mer":
        return sub_location
    if sub_location and sub_location != "France":
        return f"{location} : {sub_location}"
    return location


def add_display_name(factors):
    try_adding_display_name(factors, lambda factor: factor["type"], lambda factor: True)
    try_adding_display_name(
        factors, name_and_attribute, lambda factor: not factor.get("affichage") and factor.get("attribut")
    )
    try_adding_display_name(
        factors,
        name_and_attribute_and_border,
        lambda factor: not factor.get("affichage") and factor.get("attribut") and factor.get("frontière"),
    )
    for (key, factor) in factors.items():
        if not factor.get("affichage"):
            factor["affichage"] = key  # key must be unique, so take that as fallback
        del factor["attribut"]
        del factor["frontière"]
        del factor["type"]


def name_and_attribute(factor):
    return f"{factor['type']}, {factor['attribut']}"


def name_and_border(factor):
    return f"{factor['type']}, {factor['frontière']}"


def name_and_attribute_and_border(factor):
    return f"{factor['type']}, {factor['attribut']}, {factor['frontière']}"


def try_adding_display_name(factors, name_func, valid_data):
    unique_names = {}
    duplicate_names = []
    for (key, factor) in factors.items():
        if not valid_data(factor):
            continue
        name = name_func(factor)
        if name not in unique_names:
            if name not in duplicate_names:
                unique_names[name] = key
        else:
            del unique_names[name]
            duplicate_names.append(name)
    for key in unique_names.values():
        factors[key]["affichage"] = name_func(factors[key])


# results = ƒetch_emissions()
results = read_emissions_file("./files/Base.Carbone.V20.2_Extrait.BCS-1.csv")
factors = create_emission_factors_file(results)
