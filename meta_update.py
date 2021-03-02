# Outline ttl file parser to generate new index.yaml file for ocred pechas.
import csv
import logging
import re
import requests
import pyewts
import uuid
import yaml

from pathlib import Path
from rdflib import Graph
from rdflib.namespace import RDF, RDFS, SKOS, OWL, Namespace, NamespaceManager, XSD

BDR = Namespace("http://purl.bdrc.io/resource/")
BDO = Namespace("http://purl.bdrc.io/ontology/core/")
BDA = Namespace("http://purl.bdrc.io/admindata/")
ADM = Namespace("http://purl.bdrc.io/ontology/admin/")
EWTSCONV = pyewts.pyewts()

logging.basicConfig(filename="meta_update.log", level=logging.DEBUG, filemode="w")


def from_yaml(path):
    """Load yaml to list.
    Args:
        vol_path (path): base path object
        type (string): 
    """
    index_yaml = yaml.safe_load(path.read_text(encoding="utf-8"))
    return index_yaml


def get_ttl(work_id):
    """Download ttl file of work and save in meta_ttl.

    Args:
        work_id (str): work id
    """
    print("Downloading ttl file")
    try:
        ttl = requests.get(f"http://purl.bdrc.io/graph/{work_id}.ttl")
        return ttl.text
    except:
        print(' TTL not Found!!!')
        return ""

def get_old_meta(opf_id):
    """Download meta.yml of given opf.
    
    Args:
        opf_id (str): openpecha id example P000100
    """
    old_meta = requests.get(f"https://raw.githubusercontent.com/OpenPecha/{opf_id}/master/{opf_id}.opf/meta.yml")
    old_meta = yaml.safe_load(old_meta.text)
    return old_meta

def get_img_grp_id(URI):
    """Extract image group id from URI.

    Args:
        URI (str): URI

    Returns:
        str: image group id from URI
    """
    return URI.split("/")[-1]


def get_vol_img_grp_id_list(g, work_id):
    """Produce a list of volume's image group id wihc belongs to given work id.

    Args:
        g (graph): graph in which the node exist
        Work_id (str): Work_id in the graph g

    Returns:
        list: list of volume node
    """
    vol_img_grp_ids = []
    volumes = g.objects(BDR[work_id], BDO["instanceHasVolume"])
    for volume in volumes:
        vol_img_grp_id = get_img_grp_id(str(volume))
        vol_img_grp_ids.append(vol_img_grp_id)
    vol_img_grp_ids.sort()
    return vol_img_grp_ids


def ewtstobo(ewtsstr):
    """Convert wylie tibetan to unicode tibetan character.

    Args:
        ewtsstr (str): wylie tibetan string

    Returns:
        str: equivalent unicode tibetan character of wylie transliteration
    """
    res = EWTSCONV.toUnicode(ewtsstr)
    return res


def parse_volume_info(meta_ttl, work_id):
    """Parse the information of ttl file of given work id.

    Args:
        work_id (str): work id

    Returns:
        dict: Information of texts such as title, volume number and total number of pages in a volume
    """
    g = Graph()
    try:
        g.parse(data=meta_ttl, format="ttl")
    except:
        logging.warning(f"{work_id}.ttl Contains bad syntax")
        return {}
    vol_img_grp_ids = get_vol_img_grp_id_list(g, work_id)
    vol_info = {}
    for vol_img_grp_id in vol_img_grp_ids:
        uid = uuid.uuid4().hex
        title = g.value(BDR[vol_img_grp_id], RDFS.comment)
        if title:
            title = title.value
        else:
            logging.warning(f"{vol_img_grp_id} in work id: {work_id} doesn't have proper title")
            title = ""
        volume_number = int(g.value(BDR[vol_img_grp_id], BDO["volumeNumber"]))
        try:
            total_pages = int(g.value(BDR[vol_img_grp_id], BDO["volumePagesTotal"]))
        except:
            total_pages = 0
        vol_info[uid] = {
            "image_group_id": vol_img_grp_id,
            "title": title,
            "volume_number": volume_number,
            "total_pages": total_pages,
        }
    return vol_info


def get_new_meta(old_meta, meta_ttl, work_id):
    """Generate updated meta data of a work which include volume info by parsing ttl file of work.

    Args:
        old_meta (dict): old meta data of opf
        meta_ttl (str): meta of given work id in ttl format
        work_id (str): work id

    Returns:
        dict: updated meta data which include volume info.
    """
    volume_info = parse_volume_info(meta_ttl, work_id)
    try:
        old_meta["source_metadata"]["volume"] = volume_info
    except:
        logging.warning(f"{work_id} doesn't have proper meta.yml")
    return old_meta



if __name__ == "__main__":
    # with open("catalog.csv", newline="") as csvfile:
    #     pechas = csv.reader(csvfile, delimiter=",")
    #     for pecha in pechas:
            # opf_id = re.search("\[.+\]", pecha[0])[0][1:-1]
            # bdrc_id = re.search("bdr:(.+)", pecha[-1]).group(1)
    opf_id = "P000003"
    bdrc_work_id = "W22083"
    meta_ttl = get_ttl(bdrc_work_id)
    old_meta = get_old_meta(opf_id)
    new_meta = get_new_meta(old_meta, meta_ttl, bdrc_work_id)
    new_meta_yaml = yaml.safe_dump(
        new_meta, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    # New_meta_yaml can be saved directly on repo of respective opf.
    Path(f"./new_meta/{opf_id}").mkdir(parents=True, exist_ok=True)
    Path(f"./new_meta/{opf_id}/meta.yml").write_text(new_meta_yaml, encoding="utf-8")
    logging.info(f"{opf_id}.. Completed")
