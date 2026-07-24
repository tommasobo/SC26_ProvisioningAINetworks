from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


ALGO_LABEL = {0: "tree", 1: "ring"}
PROTO_LABEL = {0: "ll", 1: "ll128", 2: "simple"}
CONTEXT_LABELS = {"Other": 0, "PP": 1, "DP": 2}


def _gpu_order(comm_info: pd.DataFrame) -> Dict[Tuple[str, int], int]:
    rows = [
        (str(row["nodeId"]), int(row["pid"]))
        for _, row in comm_info[["nodeId", "pid"]].drop_duplicates().iterrows()
    ]
    rows.sort(key=lambda item: ((0, int(item[0])) if item[0].isdigit() else (1, item[0]), item[1]))
    out: Dict[Tuple[str, int], int] = {}
    for idx, (node_raw, pid) in enumerate(rows):
        out[(node_raw, pid)] = idx
        if node_raw.isdigit():
            out[(str(int(node_raw)), pid)] = idx
            out[(node_raw.zfill(6), pid)] = idx
    return out


def _channel_bytes(kernel_rows: pd.DataFrame, type_size: int) -> Tuple[str, str]:
    if kernel_rows.empty:
        return "", ""
    ordered = kernel_rows.sort_values("workOffset")
    work = ",".join(str(int(row["workCount"]) * type_size) for _, row in ordered.iterrows())
    chunk = ",".join(str(int(row["chunkCount"]) * type_size) for _, row in ordered.iterrows())
    return work, chunk


def write_collective_instances_from_output_dir(output_dir: Path, output_csv: Path | None = None) -> Path:
    output_dir = output_dir.resolve()
    output_csv = output_csv.resolve() if output_csv is not None else output_dir / "collective_instances.csv"

    comm_info = pd.read_csv(output_dir / "comm_info.csv")
    gpu_to_goal_rank = _gpu_order(comm_info)
    participant_rank = {
        (
            str(row["commId"]),
            str(int(row["nodeId"])) if str(row["nodeId"]).isdigit() else str(row["nodeId"]),
            int(row["pid"]),
        ): int(row["rank"])
        for _, row in comm_info.iterrows()
    }
    nranks_by_comm = {
        str(comm_id): int(group["rank"].nunique())
        for comm_id, group in comm_info.groupby("commId")
    }
    comm_num_id = {
        str(comm_id): idx
        for idx, comm_id in enumerate(comm_info["commId"].drop_duplicates().tolist())
    }

    comm_data_dir = output_dir / "comm_data"
    coll_info_dir = output_dir / "coll_info"
    coll_kernels_dir = output_dir / "coll_kernels"

    rows: List[Dict[str, object]] = []
    for comm_data_file in sorted(comm_data_dir.glob("*.csv")):
        node_id, pid = comm_data_file.stem.split("_", 1)
        pid_int = int(pid)
        node_key = str(int(node_id)) if str(node_id).isdigit() else str(node_id)
        goal_rank = gpu_to_goal_rank[(node_key, pid_int)]
        comm_df = pd.read_csv(comm_data_file).sort_values(
            ["commId", "collective", "start", "end", "eventId"]
        ).reset_index(drop=True)
        comm_df = comm_df.dropna(subset=["commId", "collective", "eventId", "start", "end"])
        if comm_df.empty:
            continue
        comm_df["instance_ordinal"] = comm_df.groupby(["commId", "collective"]).cumcount()

        coll_info_file = coll_info_dir / comm_data_file.name
        coll_info_df = pd.read_csv(coll_info_file) if coll_info_file.exists() else pd.DataFrame()
        coll_map = {
            int(row["association"]): row
            for row in coll_info_df.to_dict("records")
        } if not coll_info_df.empty else {}

        coll_kernels_file = coll_kernels_dir / comm_data_file.name
        coll_kernels_df = pd.read_csv(coll_kernels_file) if coll_kernels_file.exists() else pd.DataFrame()
        kernel_map = {
            int(assoc): group
            for assoc, group in coll_kernels_df.groupby("association")
        } if not coll_kernels_df.empty else {}

        for _, event in comm_df.iterrows():
            assoc = int(event["eventId"])
            comm_id = str(event["commId"])
            collective = str(event["collective"])
            ordinal = int(event["instance_ordinal"])
            parallelism = str(event["parallelism"]) if "parallelism" in event and not pd.isna(event["parallelism"]) else "Other"
            base = {
                "nodeId": node_key,
                "pid": pid_int,
                "goal_rank": goal_rank,
                "participant": participant_rank[(comm_id, node_key, pid_int)],
                "nranks": nranks_by_comm[comm_id],
                "eventId": assoc,
                "commId": comm_id,
                "collective": collective,
                "stream": str(event["stream"]),
                "start": int(event["start"]),
                "end": int(event["end"]),
                "groupId": int(event["groupId"]) if "groupId" in event and not pd.isna(event["groupId"]) else -1,
                "parallelism": parallelism,
                "context_label": CONTEXT_LABELS.get(parallelism, 0) + comm_num_id[comm_id] * 100,
                "instance_ordinal": ordinal,
                "instance_id": f"{comm_id}_{collective.lower()}_{ordinal}",
            }
            if assoc in coll_map:
                coll = coll_map[assoc]
                type_size = int(coll["type_size"])
                kernel_rows = kernel_map.get(assoc, pd.DataFrame())
                channel_work_bytes, channel_chunk_bytes = _channel_bytes(kernel_rows, type_size)
                base.update(
                    {
                        "algo": ALGO_LABEL.get(int(coll["algo"]), str(coll["algo"])),
                        "proto": PROTO_LABEL.get(int(coll["proto"]), str(coll["proto"])),
                        "root": int(coll["root"]),
                        "redOp": int(coll["redOp"]),
                        "data_size": int(coll["data_size"]),
                        "type_size": type_size,
                        "chunkSteps": int(coll["chunkSteps"]),
                        "sliceSteps": int(coll["sliceSteps"]),
                        "stepSize": int(coll["stepSize"]),
                        "channels": int(len(kernel_rows)) if not kernel_rows.empty else 0,
                        "channel_work_bytes": channel_work_bytes,
                        "channel_chunk_bytes": channel_chunk_bytes,
                    }
                )
            else:
                base.update(
                    {
                        "algo": None,
                        "proto": None,
                        "root": None,
                        "redOp": None,
                        "data_size": None,
                        "type_size": None,
                        "chunkSteps": None,
                        "sliceSteps": None,
                        "stepSize": None,
                        "channels": None,
                        "channel_work_bytes": "",
                        "channel_chunk_bytes": "",
                    }
                )
            rows.append(base)

    out_df = pd.DataFrame(rows)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_csv, index=False)
    return output_csv
