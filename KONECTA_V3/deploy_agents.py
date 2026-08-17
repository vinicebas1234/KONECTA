#!/usr/bin/env python3
"""
KONECTA Intelligence Hub - Auto Deploy Agents
Script Python para deploy automático de agents no Orca
"""

import json
import os
import re
import sys
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Colors
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_colored(message: str, color: str = Colors.RESET):
    """Print colored message"""
    print(f"{color}{message}{Colors.RESET}")

def print_header():
    """Print header"""
    print_colored("\n╔════════════════════════════════════════════════════════════════╗", Colors.CYAN)
    print_colored("║   KONECTA Intelligence Hub - Deploy Agents (Automático)      ║", Colors.CYAN)
    print_colored("╚════════════════════════════════════════════════════════════════╝", Colors.CYAN)

def read_agent_scripts(script_file: Path) -> Dict[str, str]:
    """Read and parse AGENT_SCRIPTS.md"""
    if not script_file.exists():
        print_colored(f"❌ Erro: {script_file} não encontrado", Colors.RED)
        return {}

    content = script_file.read_text(encoding='utf-8')

    # Extract agents
    agents = {}

    # Pattern: ## 🔵 CLAUDE (Architecture & Synthesis)
    # ... content ...
    # ```
    # Script content
    # ```

    pattern = r'##\s+[🔵🟠🌐🔴💎🎨]\s+(\w+)[^`]*```\n(.*?)\n```'

    matches = re.finditer(pattern, content, re.DOTALL)
    for match in matches:
        agent_name = match.group(1).lower()
        script_content = match.group(2).strip()
        agents[agent_name] = script_content

    return agents

def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard"""
    try:
        # Windows
        if sys.platform == 'win32':
            import subprocess
            process = subprocess.Popen(
                ['powershell', '-Command', 'Set-Clipboard'],
                stdin=subprocess.PIPE,
                encoding='utf-8'
            )
            process.communicate(input=text)
            return process.returncode == 0

        # macOS
        elif sys.platform == 'darwin':
            import subprocess
            process = subprocess.Popen(
                ['pbcopy'],
                stdin=subprocess.PIPE,
                encoding='utf-8'
            )
            process.communicate(input=text)
            return process.returncode == 0

        # Linux
        elif sys.platform == 'linux':
            import subprocess
            try:
                subprocess.run(
                    ['xclip', '-selection', 'clipboard'],
                    input=text.encode('utf-8'),
                    check=True
                )
                return True
            except:
                try:
                    subprocess.run(
                        ['xsel', '--clipboard', '--input'],
                        input=text.encode('utf-8'),
                        check=True
                    )
                    return True
                except:
                    return False
    except Exception as e:
        print_colored(f"⚠️  Erro ao copiar: {e}", Colors.YELLOW)
        return False

def create_orca_worktree(agent_name: str, script: str, branch: str, dry_run: bool = False) -> bool:
    """Create Orca worktree"""
    if dry_run:
        print_colored(f"  🔍 [DRY RUN] Worktree não será criado", Colors.YELLOW)
        return True

    try:
        # Try to use Orca CLI
        # This requires Orca to be installed and in PATH
        cmd = [
            'orca', 'create-worktree',
            '--agent', agent_name,
            '--branch', branch,
            '--project', 'KONECTA_V3'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            print_colored(f"  ✅ Worktree criado com sucesso!", Colors.GREEN)
            return True
        else:
            print_colored(f"  ⚠️  Orca CLI retornou: {result.stderr}", Colors.YELLOW)
            return False

    except FileNotFoundError:
        print_colored(f"  ⚠️  Orca CLI não encontrado (esperado)", Colors.YELLOW)
        return False
    except subprocess.TimeoutExpired:
        print_colored(f"  ⏱️  Timeout ao criar worktree", Colors.YELLOW)
        return False
    except Exception as e:
        print_colored(f"  ❌ Erro: {e}", Colors.RED)
        return False

def deploy_agent(
    agent_name: str,
    script: str,
    branch: str,
    display_name: str,
    dry_run: bool = False
) -> bool:
    """Deploy single agent"""
    print_colored(f"\n🚀 Deployando: {display_name}", Colors.CYAN)
    print_colored("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", Colors.CYAN)

    if not script:
        print_colored(f"❌ Script vazio para {agent_name}", Colors.RED)
        return False

    print_colored(f"  📋 Script: {len(script)} caracteres", Colors.BLUE)

    # Copia para clipboard
    if copy_to_clipboard(script):
        print_colored(f"  ✅ Copiado para clipboard!", Colors.GREEN)
    else:
        print_colored(f"  ⚠️  Falha ao copiar para clipboard", Colors.YELLOW)

    # Cria worktree
    if create_orca_worktree(agent_name, script, branch, dry_run):
        print_colored(f"  ✅ Pronto para {agent_name}!", Colors.GREEN)
        return True
    else:
        print_colored(f"  ⚠️  Use o script copiado manualmente no Orca", Colors.YELLOW)
        return True

def show_menu() -> str:
    """Show interactive menu"""
    print_colored("\n📋 Escolha um agent:", Colors.CYAN)
    print("  1. 🔵 CLAUDE       - Architecture Review")
    print("  2. 🟠 CODEX        - Motor Optimization")
    print("  3. 🌐 GEMINI       - Vision Motor")
    print("  4. 🔴 GROK         - Context Engine")
    print("  5. 💎 OPENCODE #1  - Code Quality")
    print("  6. 💎 OPENCODE #2  - Testing Suite")
    print("  7. 🎨 CURSOR       - UI Polish")
    print("  8. 💎 OPENCODE #3  - Backend Setup")
    print("  9. 🚀 TODOS")
    print("  0. ❌ Sair")
    print()

    choice = input("Digite sua escolha (0-9): ").strip()
    return choice

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='KONECTA Intelligence Hub - Deploy Agents'
    )
    parser.add_argument(
        '--agent',
        choices=['all', 'claude', 'codex', 'gemini', 'grok', 'opencode1', 'opencode2', 'cursor', 'opencode3'],
        default='all',
        help='Agent para deploy'
    )
    parser.add_argument('--dry-run', action='store_true', help='Simular sem executar')
    parser.add_argument('--parallel', action='store_true', help='Deploy paralelo (beta)')
    parser.add_argument('--interactive', '-i', action='store_true', help='Modo interativo')

    args = parser.parse_args()

    # Header
    print_header()

    print_colored("\n⚠️  IMPORTANTE: NÃO MEXER EM SIGNLAB!", Colors.YELLOW)
    print("Todos os agents vão trabalhar APENAS em KONECTA_V3\n")

    # Read scripts
    script_dir = Path(__file__).parent
    agent_scripts_file = script_dir / 'AGENT_SCRIPTS.md'

    print_colored(f"📖 Lendo: {agent_scripts_file.name}", Colors.BLUE)
    agents_data = read_agent_scripts(agent_scripts_file)

    if not agents_data:
        print_colored("❌ Nenhum agent encontrado!", Colors.RED)
        return 1

    print_colored(f"✅ Encontrados {len(agents_data)} agents\n", Colors.GREEN)

    # Define agent configs
    agents_config = {
        'claude': ('develop', '🔵 CLAUDE - Architecture Review'),
        'codex': ('feature/motor-optimizations', '🟠 CODEX - Motor Optimization'),
        'gemini': ('feature/gemini-vision-validation', '🌐 GEMINI - Vision Motor'),
        'grok': ('feature/grok-context', '🔴 GROK - Context Engine'),
        'opencode1': ('chore/code-quality', '💎 OPENCODE #1 - Code Quality'),
        'opencode2': ('feature/test-coverage', '💎 OPENCODE #2 - Testing Suite'),
        'cursor': ('feature/ui-improvements', '🎨 CURSOR - UI Polish'),
        'opencode3': ('feature/backend-infrastructure', '💎 OPENCODE #3 - Backend Setup'),
    }

    # Modo interativo
    if args.interactive or len(sys.argv) == 1:
        choice = show_menu()

        if choice == '0':
            print("\n👋 Saindo...")
            return 0
        elif choice == '9':
            args.agent = 'all'
        elif '1' <= choice <= '8':
            agent_list = ['claude', 'codex', 'gemini', 'grok', 'opencode1', 'opencode2', 'cursor', 'opencode3']
            args.agent = agent_list[int(choice) - 1]
        else:
            print_colored("❌ Opção inválida!", Colors.RED)
            return 1

    # Deploy
    if args.agent == 'all':
        print_colored("\n🚀 Deployando TODOS os agents...\n", Colors.GREEN)

        success_count = 0
        for agent_name, (branch, display) in agents_config.items():
            script = agents_data.get(agent_name, '')
            if deploy_agent(agent_name, script, branch, display, args.dry_run):
                success_count += 1

        print_colored(f"\n✅ {success_count}/{len(agents_config)} agents prontos!", Colors.GREEN)
    else:
        agent_name = args.agent
        if agent_name in agents_config:
            branch, display = agents_config[agent_name]
            script = agents_data.get(agent_name, '')
            deploy_agent(agent_name, script, branch, display, args.dry_run)

    # Footer
    print_colored("\n╔════════════════════════════════════════════════════════════════╗", Colors.GREEN)
    print_colored("║                    ✅ DEPLOYMENT COMPLETO!                   ║", Colors.GREEN)
    print_colored("╚════════════════════════════════════════════════════════════════╝", Colors.GREEN)

    print_colored("\n📝 Próximos passos:", Colors.CYAN)
    print("  1. Abra Orca: C:\\Users\\vrsantos\\.claude\\orca")
    print("  2. Crie worktree (Ctrl+Shift+W)")
    print("  3. Cole o script (Ctrl+V está no clipboard)")
    print("  4. Clique 'Create worktree'")
    print("  5. Agent vai começar a trabalhar!")

    print_colored("\n💡 Dicas:", Colors.YELLOW)
    print("  • Execute com --dry-run para simular")
    print("  • Use --interactive para menu visual")
    print("  • Scripts já estão no clipboard!\n")

    return 0

if __name__ == '__main__':
    sys.exit(main())
