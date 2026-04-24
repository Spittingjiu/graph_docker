#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
import sys
import json
import datetime
from urllib.parse import quote

import requests

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
MS_GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"

DEFAULT_FULL_SCOPES = [
    "User.Read",
    "Mail.Read",
    "Mail.ReadWrite",
    "MailboxSettings.Read",
    "MailboxSettings.ReadWrite",
    "Files.Read.All",
    "Files.ReadWrite.All",
    "Sites.Read.All",
    "Sites.ReadWrite.All",
    "Directory.Read.All",
    "Directory.ReadWrite.All",
]

DEFAULT_LITE_SCOPES = ["User.Read"]


def eprint(msg: str):
    print(msg, file=sys.stderr)


def graph_request(method: str, url: str, token: str, **kwargs):
    headers = kwargs.pop("headers", {})
    headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    )
    resp = requests.request(method, url, headers=headers, timeout=20, **kwargs)
    if resp.status_code >= 400:
        raise RuntimeError(f"Graph API {method} {url} failed: {resp.status_code} {resp.text[:800]}")
    if resp.text:
        return resp.json()
    return {}


def get_graph_scope_map(token: str):
    url = f"{GRAPH_BASE}/servicePrincipals(appId='{MS_GRAPH_APP_ID}')?$select=id,oauth2PermissionScopes"
    js = graph_request("GET", url, token)
    sp_id = js["id"]
    scopes = js.get("oauth2PermissionScopes", [])
    scope_map = {s.get("value"): s.get("id") for s in scopes if s.get("value") and s.get("id")}
    return sp_id, scope_map


def build_required_resource_access(scope_values, scope_map):
    resource_access = []
    missing = []
    for scope in scope_values:
        scope_id = scope_map.get(scope)
        if not scope_id:
            missing.append(scope)
            continue
        resource_access.append({"id": scope_id, "type": "Scope"})

    if missing:
        raise RuntimeError(f"这些 scope 在 Graph 中未找到: {missing}")

    return [
        {
            "resourceAppId": MS_GRAPH_APP_ID,
            "resourceAccess": resource_access,
        }
    ]


def create_application(token: str, display_name: str, redirect_uri: str, required_resource_access):
    body = {
        "displayName": display_name,
        "signInAudience": "AzureADandPersonalMicrosoftAccount",
        "web": {"redirectUris": [redirect_uri]},
        "requiredResourceAccess": required_resource_access,
    }
    return graph_request("POST", f"{GRAPH_BASE}/applications", token, data=json.dumps(body))


def create_service_principal(token: str, app_id: str):
    body = {"appId": app_id}
    return graph_request("POST", f"{GRAPH_BASE}/servicePrincipals", token, data=json.dumps(body))


def add_password(token: str, app_object_id: str):
    now = datetime.datetime.utcnow()
    end = now + datetime.timedelta(days=730)
    body = {
        "passwordCredential": {
            "displayName": "graph_docker_secret",
            "endDateTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    }
    return graph_request(
        "POST",
        f"{GRAPH_BASE}/applications/{app_object_id}/addPassword",
        token,
        data=json.dumps(body),
    )


def upsert_env(path: str, updates: dict):
    existing = {}
    lines = []

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        for line in lines:
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            existing[k] = v

    existing.update({k: str(v) for k, v in updates.items() if v is not None})

    # 保留注释结构，替换已存在键，末尾补充缺失键
    out_lines = []
    seen = set()
    for line in lines:
        if not line or line.strip().startswith("#") or "=" not in line:
            out_lines.append(line)
            continue
        k, _ = line.split("=", 1)
        if k in existing:
            out_lines.append(f"{k}={existing[k]}")
            seen.add(k)
        else:
            out_lines.append(line)

    for k, v in existing.items():
        if k not in seen:
            out_lines.append(f"{k}={v}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines).rstrip() + "\n")


def main():
    print("=== graph_docker tenant-init 向导 ===")
    print("功能：自动创建 Entra 应用、配置权限、生成 secret、写入 .env")
    print("注意：仍需管理员手动完成一次 admin consent。\n")

    bootstrap_token = os.getenv("GRAPH_BOOTSTRAP_TOKEN", "").strip()
    if not bootstrap_token:
        bootstrap_token = input("请输入 Graph Bootstrap Token（具备 Application.ReadWrite.All 等权限）: ").strip()
    if not bootstrap_token:
        raise RuntimeError("未提供 GRAPH_BOOTSTRAP_TOKEN")

    tenant_id = os.getenv("TENANT_ID", "common").strip() or "common"
    redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:53682/").strip() or "http://localhost:53682/"
    graph_profile = (os.getenv("GRAPH_API_PROFILE", "full").strip() or "full").lower()
    display_name = os.getenv("APP_DISPLAY_NAME", "graph_docker_auto").strip() or "graph_docker_auto"

    print("\n[1/5] 拉取 Microsoft Graph scope 映射...")
    _, scope_map = get_graph_scope_map(bootstrap_token)

    if graph_profile == "lite":
        wanted_scopes = DEFAULT_LITE_SCOPES
    else:
        wanted_scopes = DEFAULT_FULL_SCOPES

    print(f"[2/5] 构建权限集合（profile={graph_profile}）...")
    required_resource_access = build_required_resource_access(wanted_scopes, scope_map)

    print("[3/5] 创建应用注册...")
    app = create_application(
        bootstrap_token,
        display_name=display_name,
        redirect_uri=redirect_uri,
        required_resource_access=required_resource_access,
    )

    app_id = app["appId"]
    app_object_id = app["id"]

    print("[4/5] 创建服务主体 + 生成 client secret...")
    try:
        create_service_principal(bootstrap_token, app_id)
    except Exception as e:
        eprint(f"创建 service principal 警告（可忽略一次性冲突）: {e}")

    pwd = add_password(bootstrap_token, app_object_id)
    client_secret = pwd.get("secretText")
    if not client_secret:
        raise RuntimeError("生成 client secret 失败")

    print("[5/5] 写入 .env ...")
    env_path = ".env"
    if not os.path.exists(env_path) and os.path.exists(".env.example"):
        with open(".env.example", "r", encoding="utf-8") as src, open(env_path, "w", encoding="utf-8") as dst:
            dst.write(src.read())

    upsert_env(
        env_path,
        {
            "CLIENT_ID": app_id,
            "CLIENT_SECRET": client_secret,
            "TENANT_ID": tenant_id,
            "REDIRECT_URI": redirect_uri,
            "GRAPH_API_PROFILE": graph_profile,
        },
    )

    admin_consent_url = (
        f"https://login.microsoftonline.com/{tenant_id}/adminconsent"
        f"?client_id={quote(app_id)}&redirect_uri={quote(redirect_uri)}"
    )

    print("\n✅ 初始化完成")
    print(f"应用名: {display_name}")
    print(f"CLIENT_ID: {app_id}")
    print("CLIENT_SECRET: 已写入 .env")
    print(f"权限模式: {graph_profile} -> {', '.join(wanted_scopes)}")
    print("\n[必须先完成] 管理员 consent 链接：")
    print(admin_consent_url)
    print("\n请先在浏览器完成 consent，再继续后续步骤。")


if __name__ == "__main__":
    main()
