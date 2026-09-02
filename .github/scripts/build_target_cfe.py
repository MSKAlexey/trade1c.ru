from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import shutil
import subprocess
import urllib.request

ROOT = pathlib.Path.cwd()
BASE_CFE = ROOT / "base.cfe"
QUERY_CFE = ROOT / "queryconsole.cfe"
SRC = ROOT / "source"
QUERY_SRC = ROOT / "query_source"
VERIFY = ROOT / "verify"
OUT = ROOT / "АНЬДЭЛИ_ЭЛЕКТРИК_РУС_УПД_ЭТМ.cfe"

BASE_BLOB_URL = "https://api.github.com/repos/emakei/cfe/git/blobs/a26ed4eddc722f7bd7d70028afb7b4cba19d7e8a"
QUERY_URL = (
    "https://github.com/pulh1/QueryConsole1C/releases/download/beta/"
    "QueryConsoleZUP-0.5.0.1.cfe"
)

BASE_MODULE_UUID = "05e9c698-9fe8-4b3e-b9d9-dc02b458fed6"
MODULE_NAME = "ОбменСКонтрагентамиПереопределяемый"
EXTENSION_NAME = "АЭР_УПДЭТМ"
EXTENSION_SYNONYM = "УПД ЭТМ — ООО «АНЬДЭЛИ ЭЛЕКТРИК РУС»"
EXTENSION_COMMENT = (
    "Добавляет в исходящий УПД для ЭТМ ИдГрузПолуч=4660011515045 "
    "и ЗаказНомер из номера заказа по данным клиента."
)
EXTENSION_PREFIX = "АЭР_"
NEW_FILE_UUID = "f5d3d06c-49a2-4a75-ae1c-9fb23800c5e2"
BSL_PATH = ROOT / ".github" / "scripts" / "АЭР_УПД_ЭТМ_Module.bsl"


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, check=True)


def download_github_blob(url: str, target: pathlib.Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "cfe-builder"},
    )
    with urllib.request.urlopen(request) as response:
        payload = json.load(response)
    target.write_bytes(base64.b64decode(payload["content"]))


def replace_strings(value, replacements: dict[str, str]):
    if isinstance(value, dict):
        return {k: replace_strings(v, replacements) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_strings(v, replacements) for v in value]
    if isinstance(value, str):
        for old, new in replacements.items():
            value = value.replace(old, new)
        return value
    return value


def main() -> None:
    for p in (SRC, QUERY_SRC, VERIFY):
        if p.exists():
            shutil.rmtree(p)
    for p in (BASE_CFE, QUERY_CFE, OUT):
        if p.exists():
            p.unlink()

    download_github_blob(BASE_BLOB_URL, BASE_CFE)
    urllib.request.urlretrieve(QUERY_URL, QUERY_CFE)

    run("v8unpack", "-E", str(BASE_CFE), str(SRC), "--processes", "1")
    run("v8unpack", "-E", str(QUERY_CFE), str(QUERY_SRC), "--processes", "1")

    for child in list(SRC.iterdir()):
        if child.name not in {"ConfigurationExtension.json", "version.bin", "Language"}:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    sample = QUERY_SRC / "CommonModule" / "ГенерацияИсполняемогоКодаПредставленийЗУПУтилиты"
    target_module = SRC / "CommonModule" / MODULE_NAME
    target_module.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(sample, target_module)

    id_path = target_module / "CommonModule.id.json"
    id_data = json.loads(id_path.read_text(encoding="utf-8"))
    id_data["uuid"] = BASE_MODULE_UUID
    id_path.write_text(json.dumps(id_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    module_path = target_module / "CommonModule.json"
    module_data = json.loads(module_path.read_text(encoding="utf-8"))
    old_module_name = module_data["name"]
    old_module_synonym = module_data.get("name2", {}).get("ru", old_module_name)
    module_data = replace_strings(module_data, {
        old_module_name: MODULE_NAME,
        old_module_synonym: "Обмен с контрагентами переопределяемый",
    })
    module_data["name"] = MODULE_NAME
    module_data["name2"] = {"ru": "Обмен с контрагентами переопределяемый"}
    module_data["comment"] = EXTENSION_COMMENT
    module_data["header"][0][1][2:] = ["1", "1", "1", "0", "0", "0", "0", "0"]
    module_path.write_text(json.dumps(module_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    bsl = BSL_PATH.read_text(encoding="utf-8")
    (target_module / "CommonModule.obj.bsl").write_text("\ufeff" + bsl, encoding="utf-8")

    root_path = SRC / "ConfigurationExtension.json"
    root_data = json.loads(root_path.read_text(encoding="utf-8"))
    old_name = root_data.get("name", "ИзменениеАлгоритмовЗагрузкиДанных")
    old_synonym = root_data.get("name2", {}).get("ru", "Изменение алгоритмов загрузки данных")
    old_uuid = root_data["file_uuid"]
    root_data = replace_strings(root_data, {
        old_name: EXTENSION_NAME,
        old_synonym: EXTENSION_SYNONYM,
        "ИАЗД_": EXTENSION_PREFIX,
        old_uuid: NEW_FILE_UUID,
    })
    root_data["name"] = EXTENSION_NAME
    root_data["name2"] = {"ru": EXTENSION_SYNONYM}
    root_data["comment"] = EXTENSION_COMMENT
    root_data["file_uuid"] = NEW_FILE_UUID
    root_path.write_text(json.dumps(root_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    run("v8unpack", "-B", str(SRC), str(OUT), "--auto_include", "--processes", "1")
    run("v8unpack", "-E", str(OUT), str(VERIFY), "--processes", "1")

    module_dirs = sorted((VERIFY / "CommonModule").glob("*"))
    assert len(module_dirs) == 1, module_dirs
    assert module_dirs[0].name == MODULE_NAME, module_dirs[0]
    assert not (VERIFY / "DataProcessor").exists()

    verify_id = json.loads((module_dirs[0] / "CommonModule.id.json").read_text(encoding="utf-8"))
    assert verify_id["uuid"] == BASE_MODULE_UUID, verify_id

    verify_module = json.loads((module_dirs[0] / "CommonModule.json").read_text(encoding="utf-8"))
    assert verify_module["name"] == MODULE_NAME, verify_module["name"]
    assert verify_module["header"][0][1][2:] == ["1", "1", "1", "0", "0", "0", "0", "0"]

    verify_bsl = (module_dirs[0] / "CommonModule.obj.bsl").read_text(encoding="utf-8-sig")
    for required in (
        '&После("ЗаполнитьДанныеУПД_5_02_ИнформацияПродавца")',
        '&После("ЗаполнитьДанныеУПД_5_03_ИнформацияПродавца")',
        '"ИдГрузПолуч", "4660011515045"',
        '"ЗаказНомер", НомерЗаказаЭТМ',
        '"5024136666"',
    ):
        assert required in verify_bsl, required

    verify_root = json.loads((VERIFY / "ConfigurationExtension.json").read_text(encoding="utf-8"))
    assert verify_root["name"] == EXTENSION_NAME, verify_root["name"]
    assert verify_root["file_uuid"] == NEW_FILE_UUID, verify_root["file_uuid"]

    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    (ROOT / "SHA256.txt").write_text(f"{digest}  {OUT.name}\n", encoding="utf-8")
    print(f"BUILT={OUT}")
    print(f"SIZE={OUT.stat().st_size}")
    print(f"SHA256={digest}")


if __name__ == "__main__":
    main()
