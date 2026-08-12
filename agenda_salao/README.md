# Agenda do Salão

Projeto inicial funcional para aprender e testar uma agenda online de salão.

## Começar no Linux Mint

1. Extraia a pasta.
2. Abra a pasta no Gestor de Ficheiros.
3. Abra um terminal nessa pasta.
4. Execute:

```bash
chmod +x run.sh
./run.sh
```

Depois abra no navegador:

- Site: http://127.0.0.1:5000
- Painel: http://127.0.0.1:5000/admin

**Palavra-passe inicial do painel:** `CB4MvxCBsr0`

Depois de entrar no painel, altere a palavra-passe.

## O que já funciona

- Página pública do salão
- Lista de serviços sem preços
- Marcação por data e horário
- Horários ocupados deixam de aparecer
- Cancelamento
- Painel privado
- Confirmar/cancelar marcações
- Bloquear dia inteiro ou intervalo de horas
- Gerir serviços
- Editar nome, endereço, contacto e horário
- Alterar palavra-passe
- Base de dados SQLite criada automaticamente
- Interface adaptada a telemóvel

## Ainda não foi ligado

- E-mail/SMS/WhatsApp
- Notificações push
- Domínio e HTTPS
- Publicação na Internet
- Backup automático
- Conta individual para clientes

Essas partes devem entrar depois de testar a versão local.

## Importante

Esta é uma versão de aprendizagem e protótipo. Não coloque na Internet nem use com dados reais de clientes sem reforçar segurança, autenticação, HTTPS, backups e proteção de dados.
