"""
=============================================================
  CLAUDIS AGENT — Agente Autônomo para Termux
=============================================================
  Instalação no Termux:
    pkg update && pkg upgrade -y
    pkg install python git -y
    pip install requests colorama

  Uso:
    python claudis_agent.py
    python claudis_agent.py --key SUA_API_KEY
    python claudis_agent.py --key SUA_API_KEY --task "finalize o teclado Claudis"
=============================================================
"""

import subprocess
import requests
import json
import os
import sys
import argparse
import time
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

# ─── Configurações ────────────────────────────────────────────────
CLAUDE_API_URL  = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL    = "claude-sonnet-4-20250514"
MAX_ITERATIONS  = 30
COMMAND_TIMEOUT = 60
LOG_FILE        = os.path.expanduser("~/claudis_agent.log")

# ─── Comandos SEMPRE bloqueados ───────────────────────────────────
BLOCKED_COMMANDS = [
    "rm -rf /", "mkfs", ":(){:|:&};:",
    "chmod -R 777 /", "dd if=/dev/zero",
]

# ─── Comandos SENSÍVEIS — sempre pedem confirmação mesmo no modo auto ──
# Qualquer comando que contenha essas strings vai pausar e pedir permissão
SENSITIVE_PATTERNS = [
    "adb install",
    "adb uninstall",
    "pm install",
    "pm uninstall",
    ".apk",
    "am start",
    "am force-stop",
    "reboot",
    "shutdown",
    "rm -rf",
    "chmod",
    "chown",
    "termux-open",
    "pkg install",
    "pkg uninstall",
    "pip install",
    "git push",          # avisar antes de qualquer push
]


def banner():
    print(Fore.CYAN + """
╔═══════════════════════════════════════════════════╗
║       CLAUDIS AGENT — Termux Edition              ║
║   IA autônoma para desenvolver o teclado 🤖⌨️      ║
╚═══════════════════════════════════════════════════╝
""")


# ═══════════════════════════════════════════════════════════════
#  LOG
# ═══════════════════════════════════════════════════════════════
def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


# ═══════════════════════════════════════════════════════════════
#  SEGURANÇA
# ═══════════════════════════════════════════════════════════════
def is_blocked(cmd: str) -> bool:
    cmd_lower = cmd.lower().strip()
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return True
    return False


def is_sensitive(cmd: str) -> bool:
    """Retorna True se o comando precisa de confirmação mesmo no modo auto."""
    cmd_lower = cmd.lower().strip()
    for pattern in SENSITIVE_PATTERNS:
        if pattern in cmd_lower:
            return True
    return False


# ═══════════════════════════════════════════════════════════════
#  NOTIFICAÇÃO DE AÇÃO SENSÍVEL
# ═══════════════════════════════════════════════════════════════
def notify_sensitive(cmd: str, reason: str = "") -> bool:
    """
    Pausa tudo, avisa o usuário com destaque e pede permissão.
    Retorna True se permitido, False se negado.
    """
    print("\n" + Fore.RED + "═" * 55)
    print(Fore.RED + "  ⚠️  AÇÃO SENSÍVEL — REQUER SUA PERMISSÃO")
    print(Fore.RED + "═" * 55)
    if reason:
        print(Fore.YELLOW + f"  Motivo: {reason}")
    print(Fore.WHITE + f"\n  Comando: {cmd}\n")
    print(Fore.CYAN + "  Isso pode modificar o seu celular ou instalar algo.")
    print(Fore.RED + "═" * 55)

    while True:
        resp = input(Fore.YELLOW + "\n  Permitir? (s = sim / n = não / ver = ver mais detalhes): ").strip().lower()
        if resp == "s":
            print(Fore.GREEN + "  ✅ Permitido!\n")
            log(f"SENSIVEL_PERMITIDO: {cmd}")
            return True
        elif resp == "n":
            print(Fore.RED + "  ❌ Negado pelo usuário.\n")
            log(f"SENSIVEL_NEGADO: {cmd}")
            return False
        elif resp == "ver":
            print(Fore.WHITE + f"\n  Comando completo:\n  {cmd}\n")
        else:
            print(Fore.RED + "  Digite 's' ou 'n'.")


# ═══════════════════════════════════════════════════════════════
#  NOTIFICAÇÃO DE APK PRONTO PARA TESTAR
# ═══════════════════════════════════════════════════════════════
def notify_apk_ready():
    """Avisa quando o APK foi compilado e está pronto para teste."""
    print("\n" + Fore.GREEN + "═" * 55)
    print(Fore.GREEN + "  🎉 APK PRONTO PARA TESTE!")
    print(Fore.GREEN + "═" * 55)
    print(Fore.WHITE + """
  O teclado Claudis foi compilado com sucesso.

  Para instalar:
  1. Abra o GitHub Actions no Chrome
  2. Baixe o artifact 'claudis-v2-debug'
  3. Instale o APK
  4. Desinstale a versão antiga primeiro!
""")
    print(Fore.GREEN + "═" * 55)
    input(Fore.CYAN + "\n  Pressione ENTER quando tiver instalado para continuar os testes... ")


# ═══════════════════════════════════════════════════════════════
#  EXECUÇÃO DE COMANDOS
# ═══════════════════════════════════════════════════════════════
def execute_command(cmd: str, auto_confirm: bool = False) -> dict:
    if not cmd or cmd.strip() == "":
        return {"stdout": "", "stderr": "", "returncode": 0}

    # Verifica bloqueio total
    if is_blocked(cmd):
        msg = f"⛔ Comando bloqueado por segurança: {cmd}"
        print(Fore.RED + msg)
        log(msg)
        return {"stdout": "", "stderr": msg, "returncode": -1}

    # Verifica se é sensível — SEMPRE pede permissão, mesmo no modo auto
    if is_sensitive(cmd):
        reason = ""
        if ".apk" in cmd.lower() or "pm install" in cmd.lower() or "adb install" in cmd.lower():
            reason = "Instalação de APK no dispositivo"
        elif "pm uninstall" in cmd.lower() or "adb uninstall" in cmd.lower():
            reason = "Desinstalação de aplicativo"
        elif "reboot" in cmd.lower():
            reason = "Reinicialização do dispositivo"
        elif "git push" in cmd.lower():
            reason = "Push para o repositório remoto"
        elif "pkg install" in cmd.lower():
            reason = "Instalação de pacote no Termux"
        else:
            reason = "Modificação do sistema"

        allowed = notify_sensitive(cmd, reason)
        if not allowed:
            return {"stdout": "", "stderr": "Negado pelo usuário.", "returncode": -1}

    elif not auto_confirm:
        # Modo interativo normal
        print(Fore.YELLOW + f"\n🔧 Claude quer executar:")
        print(Fore.WHITE   + f"   $ {cmd}")
        confirm = input(Fore.CYAN + "   Permitir? (s/n/sempre): ").strip().lower()
        if confirm == "sempre":
            auto_confirm = True
        elif confirm != "s":
            return {"stdout": "", "stderr": "Usuário cancelou.", "returncode": -1}

    print(Fore.YELLOW + f"[*] Executando: {cmd}")
    log(f"EXEC: {cmd}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            cwd=os.path.expanduser("~"),
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if stdout:
            print(Fore.GREEN + f"[out] {stdout[:500]}")
        if stderr:
            print(Fore.RED   + f"[err] {stderr[:300]}")

        log(f"STDOUT: {stdout[:300]}")
        log(f"RETURNCODE: {result.returncode}")

        # Detecta se foi um push bem-sucedido (APK compilará no Actions)
        if "git push" in cmd.lower() and result.returncode == 0:
            print(Fore.CYAN + "\n  ℹ️  Push feito! O GitHub Actions vai compilar o APK.")
            print(Fore.CYAN + "  Acompanhe em: github.com/claudis-dev/claudis-keyboard-v2/actions\n")

        return {
            "stdout": stdout[:4000],
            "stderr": stderr[:1000],
            "returncode": result.returncode,
        }

    except subprocess.TimeoutExpired:
        msg = f"Timeout após {COMMAND_TIMEOUT}s"
        print(Fore.RED + f"[✗] {msg}")
        return {"stdout": "", "stderr": msg, "returncode": -1}
    except Exception as e:
        msg = str(e)
        print(Fore.RED + f"[✗] Erro: {msg}")
        return {"stdout": "", "stderr": msg, "returncode": -1}


# ═══════════════════════════════════════════════════════════════
#  CONTEXTO DO DISPOSITIVO
# ═══════════════════════════════════════════════════════════════
def get_device_context() -> str:
    info = {}
    cmds = {
        "pwd":      "pwd",
        "user":     "whoami",
        "os":       "uname -a",
        "storage":  "df -h ~ 2>/dev/null | tail -1",
        "python":   "python --version",
        "git":      "git --version",
    }
    for key, cmd in cmds.items():
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        info[key] = r.stdout.strip()

    lines = [f"  {k}: {v}" for k, v in info.items() if v]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """Você é o Claudis Agent — agente autônomo especializado em desenvolvimento Android no Termux.

Seu foco principal: desenvolver o teclado Android "Claudis" (fork do HeliBoard) em:
  ~/claudis-keyboard-v2 (proot Ubuntu via: proot-distro login ubuntu)
  Repositório: github.com/claudis-dev/claudis-keyboard-v2

Stack:
- Kotlin + Java (Android IME)
- GitHub Actions para build (ubuntu-latest)
- API Anthropic para sugestões IA no teclado

Seu trabalho:
1. Receber uma tarefa
2. Planejar os passos
3. A cada turno, retornar UM comando shell
4. Analisar o output e decidir o próximo passo
5. Quando concluído, retornar status=done

FORMATO DE RESPOSTA (JSON obrigatório, sem markdown):
{
  "thought": "raciocínio interno",
  "command": "comando shell (ou vazio)",
  "status": "running | done | error | apk_ready",
  "summary": "resumo (só quando done)"
}

Use status="apk_ready" quando o build do GitHub Actions terminar com sucesso e o APK estiver pronto para o usuário testar.

Regras:
- Retorne APENAS JSON válido
- Um comando por vez
- Para entrar no Ubuntu: proot-distro login ubuntu -- bash -c "cd ~/claudis-keyboard-v2 && COMANDO"
- Nunca execute comandos destrutivos
- Seja direto e eficiente
- Se um comando falhar, analise o erro e adapte"""


# ═══════════════════════════════════════════════════════════════
#  CHAMADA AO CLAUDE
# ═══════════════════════════════════════════════════════════════
def call_claude(api_key: str, messages: list) -> dict:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": 1000,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }
    try:
        r = requests.post(CLAUDE_API_URL, headers=headers, json=body, timeout=60)
        r.raise_for_status()
        raw = r.json()["content"][0]["text"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)

    except json.JSONDecodeError as e:
        print(Fore.RED + f"[!] JSON inválido: {e}")
        log(f"JSON_ERROR: {e}")
        return {"thought": "erro", "command": "", "status": "error", "summary": str(e)}
    except Exception as e:
        print(Fore.RED + f"[!] Erro na API: {e}")
        log(f"API_ERROR: {e}")
        return {"thought": "erro", "command": "", "status": "error", "summary": str(e)}


# ═══════════════════════════════════════════════════════════════
#  LOOP DO AGENTE
# ═══════════════════════════════════════════════════════════════
def run_agent(api_key: str, task: str, auto_confirm: bool = False):
    print(Fore.CYAN + f"\n📋 Tarefa: {task}")
    print(Fore.CYAN + "─" * 50)
    log(f"TASK: {task}")

    ctx = get_device_context()

    initial_msg = f"""Contexto do dispositivo (Termux/Android):
{ctx}

Tarefa: {task}

Inicie o planejamento e retorne o primeiro comando."""

    messages = [{"role": "user", "content": initial_msg}]
    iteration = 0

    while iteration < MAX_ITERATIONS:
        iteration += 1
        print(Fore.YELLOW + f"\n[Passo {iteration}/{MAX_ITERATIONS}]")

        response = call_claude(api_key, messages)

        thought  = response.get("thought", "")
        command  = response.get("command", "").strip()
        status   = response.get("status", "running")
        summary  = response.get("summary", "")

        if thought:
            print(Fore.MAGENTA + f"🧠 {thought}")

        # APK pronto para testar
        if status == "apk_ready":
            notify_apk_ready()
            messages.append({"role": "assistant", "content": json.dumps(response, ensure_ascii=False)})
            messages.append({"role": "user", "content": "Usuário confirmou que instalou e testou o APK. Continue com a próxima etapa."})
            continue

        # Concluído
        if status == "done":
            print(Fore.GREEN + "\n✅ TAREFA CONCLUÍDA!")
            if summary:
                print(Fore.WHITE + f"\n📊 Resumo:\n{summary}")
            log(f"DONE: {summary}")
            break

        # Erro
        if status == "error":
            print(Fore.RED + f"\n❌ Erro: {summary}")
            log(f"AGENT_ERROR: {summary}")
            break

        messages.append({
            "role": "assistant",
            "content": json.dumps(response, ensure_ascii=False)
        })

        if command:
            result = execute_command(command, auto_confirm=auto_confirm)
            output_feedback = f"""Comando: {command}
stdout: {result['stdout'] or '(vazio)'}
stderr: {result['stderr'] or '(nenhum)'}
returncode: {result['returncode']}"""
        else:
            output_feedback = "Nenhum comando executado neste passo."

        messages.append({"role": "user", "content": output_feedback})
        time.sleep(0.5)

    else:
        print(Fore.RED + f"\n⚠️  Limite de {MAX_ITERATIONS} passos atingido.")
        log("MAX_ITERATIONS reached")

    print(Fore.CYAN + f"\n📝 Log salvo em: {LOG_FILE}\n")


# ═══════════════════════════════════════════════════════════════
#  MODO INTERATIVO
# ═══════════════════════════════════════════════════════════════
def interactive_mode(api_key: str):
    banner()
    print(Fore.CYAN + "Digite uma tarefa para o agente executar.")
    print(Fore.CYAN + "Digite 'sair' para encerrar.\n")
    print(Fore.YELLOW + "Exemplos de tarefas para o teclado Claudis:")
    print("  • integre a IA do Claude nas sugestões do teclado")
    print("  • corrija o erro de compilação do último build")
    print("  • mude o tema de cores para roxo escuro")
    print("  • verifique se o build está verde no GitHub Actions\n")

    print(Fore.RED + "⚠️  ATENÇÃO: Instalação/desinstalação de APK e git push")
    print(Fore.RED + "   SEMPRE pedirão sua confirmação, mesmo no modo automático!\n")

    auto = input(Fore.CYAN + "Confirmar outros comandos? (s=sim, n=automático): ").strip().lower()
    auto_confirm = (auto == "n")

    if auto_confirm:
        print(Fore.YELLOW + "⚡ Modo automático ativo (exceto ações sensíveis)\n")
    print()

    while True:
        try:
            task = input(Fore.CYAN + "Tarefa> " + Style.RESET_ALL).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando.")
            break

        if not task:
            continue
        if task.lower() in ("sair", "exit", "quit"):
            break

        run_agent(api_key, task, auto_confirm=auto_confirm)


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Claudis Agent para Termux")
    parser.add_argument("--key",  type=str, help="Anthropic API Key")
    parser.add_argument("--task", type=str, help="Tarefa a executar")
    parser.add_argument("--auto", action="store_true", help="Modo automático (ações sensíveis sempre confirmadas)")
    args = parser.parse_args()

    api_key = args.key or os.environ.get("ANTHROPIC_API_KEY") or input("Insira sua Anthropic API Key: ").strip()
    if not api_key:
        print(Fore.RED + "API Key não fornecida.")
        sys.exit(1)

    if args.task:
        banner()
        run_agent(api_key, args.task, auto_confirm=args.auto)
    else:
        interactive_mode(api_key)
