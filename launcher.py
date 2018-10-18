import gettext
import sys
import asyncio
import pytz
import datetime
import time
import json
import emoji
import telepot
from telepot.aio.loop import MessageLoop
from telepot.aio.delegate import (
    per_chat_id, create_open, pave_event_space, include_callback_query_chat_id)
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton

class ThePokeGOBot(telepot.aio.helper.ChatHandler):
    def __init__(self, *args, **kwargs):
        super(ThePokeGOBot, self).__init__(*args, **kwargs)

        self.load_data()

        self.router.routing_table['_delete_raid'] = self.on___delete_raid
        self.router.routing_table['_delete_quest'] = self.on___delete_quest
        self.router.routing_table['_delete_help'] = self.on___delete_help
        self.router.routing_table['_delete_bot_messages'] = self.on___delete_bot_messages

    async def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)

        user = msg['from']

        if content_type != 'text':
            return

        command = msg['text'].strip()

        if command.startswith('/'):
            message = command.split(' ')
            command = message[0].strip().lower()
            del message[0]
            params = message
            await self.handle_command(command, params, user, msg)

    async def handle_command(self, cmd, params, user, user_msg):
        self.load_data()

        # Start a raid
        if cmd == _('/raid'):
            parts = " ".join(params).split(',')

            if len(parts) == 3:
                try:
                    pkmn_num = self.pokemon.index(parts[0].strip().replace('á', 'a').title())

                    if pkmn_num in self.curr_raids:
                        try:
                            time.strptime(parts[2].strip(), '%H:%M')

                            raid = {
                                'id': int(self.raids['index']) + 1,
                                'pokemon': parts[0].strip().title(),
                                'place': parts[1].strip().title(),
                                'start_time': parts[2].strip(),
                                'created_by': user,
                                'finish_by': user,
                                'status': _('active'),
                                'going': [],
                                'messages': [],
                                'comments': [],
                                'log': []
                            }

                            raid_keyboard = self.create_keyboard(raid)

                            msg = await self.sender.sendMessage(self.create_list(raid), reply_markup=raid_keyboard, parse_mode="markdown")

                            self.scheduler.event_later(self.convert_to_seconds(1, 45), ('_delete_raid', {'raid_id': raid['id']}))

                            if next((x for x in raid['messages'] if int(x['message_id']) == int(msg['message_id'])), None) == None:
                                raid['messages'].append(msg)
                            
                            self.raids["index"] = int(raid['id'])
                            self.raids["raids"].append(raid)
                            self.persist_data()                        
                        except Exception as e:
                            msg = await self.sender.sendMessage(_("Meowth! The time must be in the format of *HH:MM*!"), parse_mode="markdown")
                            self.delete_messages(msg)
                    else:
                        msg = await self.sender.sendMessage(_("Meowth! The Pokémon *%s* is not currently in the raids!") % (parts[0].strip().title()), parse_mode = "markdown")
                        self.delete_messages(msg)
                except:
                    msg = await self.sender.sendMessage(_("Meowth! *%s* is not a valid Pokémon!") % (parts[0].strip().title()), parse_mode = "markdown")
                    self.delete_messages(msg)
        # Edit the start time of the raid
        elif cmd == _('/edit'):
            if len(params) == 2:
                raid_id = int(params[0])
                new_time = params[1].strip()

                raid = next((x for x in self.raids['raids'] if int(x['id']) == raid_id), None)
                if raid == None:
                    msg = await self.sender.sendMessage(_("Meowth! The raid of id *%s* does not exist or has already ended!") % (raid_id))
                    self.delete_messages(msg)
                else:
                    try:
                        time.strptime(params[1].strip(), '%H:%M')
                        if self.exists_trainer_in_raid(raid, int(user['id'])) == True:
                            raid['start_time'] = new_time
                            self.persist_data()
                            for msg in raid['messages']:
                                await self.bot.editMessageText(telepot.message_identifier(msg), self.create_list(raid),reply_markup=self.create_keyboard(raid),parse_mode="markdown")
                        else:
                            msg = await self.sender.sendMessage(_("Meowth! You must be part of the list to use this command!"))
                            self.delete_messages(msg)
                    except:
                        msg = await self.sender.sendMessage(_("Meowth! The time must be in the format of *HH:MM*!"),parse_mode="markdown")
                        self.delete_messages(msg)
        # Edit the name raid
        elif cmd == _('/editname'):
            if len(params) == 2:
                raid_id = int(params[0])
                new_name = params[1].strip().title()

                raid = next((x for x in self.raids['raids'] if int(x['id']) == raid_id), None)
                if raid == None:
                    msg = await self.sender.sendMessage(_("Meowth! The raid of id *%s* does not exist or has already ended!") % (raid_id))
                    self.delete_messages(msg)
                else:
                    obj = next((x for x in self.raids["raids"] if int(x['id']) == int(raid_id)), None)
                    if obj == None:
                        msg = await self.sender.sendMessage(_("Meowth! The %s of id *%s* does not exist or has already ended!") % (_type, _id), parse_mode="markdown")
                        self.delete_messages(msg)
                    else:
                        if self.exists_trainer_in_raid(obj, int(user['id'])) == True:
                            raid['pokemon'] = new_name
                            self.persist_data()
                            for msg in raid['messages']:
                                await self.bot.editMessageText(telepot.message_identifier(msg), self.create_list(raid), reply_markup=self.create_keyboard(raid), parse_mode="markdown")
                        else:
                            msg = await self.sender.sendMessage(_("Meowth! You must be part of the list to use this command!"))
                            self.delete_messages(msg)
		# Cancel/finish active raid
        elif cmd == _('/cancel') or cmd == _('/end'):
            if len(params) == 1:
                command = _('cancel') if cmd == _('/cancel') else _('end')
                raid_id = params[0].strip()
                    
                if raid_id:
                    raid = next((x for x in self.raids['raids'] if int(x['id']) == int(raid_id)), None)
                    if raid == None:
                        msg = await self.sender.sendMessage(_("Meowth! The raid of id *%s* does not exist or has already ended!") % (raid_id), parse_mode = "markdown")
                        self.delete_messages(msg)
                    else:
                        if self.exists_trainer_in_raid(raid, int(user['id'])) or self.is_admin(user['id']):
                            raid['status'] = _('canceled') if command == _('cancel') else _('ended')
                            raid['finish_by'] = user
                            self.persist_data()
                            for msg in raid['messages']:
                                await self.bot.editMessageText(telepot.message_identifier(msg), self.create_list(raid), reply_markup=None, parse_mode="markdown")
                        else:
                            msg = await self.sender.sendMessage(_("Meowth! You must be part of the list to use this command!"))
                            self.delete_messages(msg)
        # Set trainer informations
        elif cmd == _('/trainer'):
            teams = [['valor', _('red'), 'v', ':fire:'], [
                'mystic', _('blue'), 'm', ':snowflake:'], ['instinct', _('yellow'), 'i', '⚡']]

            trainer = {}
            trainer_team = None
            for p in params:
                p = p.lower()
                i = 0
                for t in range(0, 3):
                    if p in teams[t]:
                        trainer['team'] = f"{teams[i][0]}"
                        trainer['emoji'] = f"{emoji.emojize(teams[i][3])}"
                        trainer_team = f"{trainer['team']} ({teams[i][1]})"
                        break
                    else:
                        i += 1

                try:
                    level = int(p)
                    if level > 0 and level <= 40:
                        trainer['level'] = level
                except:
                    continue

            if 'team' in trainer and 'level' in trainer:
                trainer['id'] = user['id']
                trainer['nickname'] = params[0].strip()
                if next((x for x in self.trainers if int(x['id']) == int(user['id'])), None) == None:
                    self.trainers.append(trainer)
                else:
                    i = 0
                    for x in self.trainers:
                        if int(x['id']) == int(user['id']):
                            self.trainers.pop(i)
                            self.trainers.append(trainer)
                            break
                        else:
                            i += 1

                self.persist_data()
                msg = await self.sender.sendMessage(_("Meowth! Team *%s* and level *%s* set!") % (trainer_team.title(), trainer['level']), parse_mode = "markdown")
                self.delete_messages(msg)
            else:
                msg = await self.sender.sendMessage(_("Meowth! Input a valid team and level!"))
                self.delete_messages(msg)
        # Update trainer's level
        elif cmd == _('/level'):
            if len(params) == 1:
                level = int(params[0].strip())
                
                if level:
                    trainer = next((x for x in self.trainers if int(x['id']) == int(user['id'])), None)
                    if trainer != None:
                        if level > 0 and level <= 40:
                            trainer['level'] = level
                            self.persist_data()
                            msg = await self.sender.sendMessage(_("Meowth! Your level was updated to *%s*!") % (level), parse_mode="markdown")
                            self.delete_messages(msg)
                        else:
                            msg = await self.sender.sendMessage(_("Meowth! Input a valid level!"))
                            self.delete_messages(msg)
                    else:
                        msg = await self.sender.sendMessage(_("Meowth! Set up your informations using */trainer team level*! This command is only for updating your level after your trainer's info are all set up!"), parse_mode = "markdown")
                        self.delete_messages(msg)
        # Post a quest report
        elif cmd == _('/quest'):
            parts = " ".join(params).split(',')

            if len(parts) == 3:
                quest = {
                    'id': int(self.quests['index']) + 1,
                    'quest': parts[0].strip().title(),
                    'place': parts[1].strip().title(),
                    'reward': parts[2].strip().title(),
                    'created_by': user,
                    'status': _('active'),
                    'messages': [],
                    'comments': []
                }

                msg = await self.sender.sendMessage(self.create_quest(quest), parse_mode="markdown")

                tomorrow = datetime.datetime.now(pytz.utc).day + 1
                midnight = datetime.datetime.now(pytz.utc).replace(day=tomorrow,hour=0,minute=0,second=0,microsecond=0)
                diff = (midnight - (datetime.datetime.now(pytz.utc) - datetime.timedelta(hours=3))).seconds

                self.scheduler.event_later(diff, ('_delete_quest', {'quest_id': quest['id']}))

                if next((x for x in quest['messages'] if int(x['message_id']) == int(msg['message_id'])), None) == None:
                    quest['messages'].append(msg)
                
                self.quests['index'] = int(quest['id'])
                self.quests['quests'].append(quest)
                self.persist_data() 
        # Share/comment raid/quest
        elif cmd == _('/share') or cmd == _('/comment'):
            if len(params) >= 2:
                try:
                    _id = int(params[1].strip())
                    _type = _("raid or quest")
                    obj = {}
                    _list = []
                    command = _('/share') if cmd == _('/share') else _('/comment')
                    parametro = params[0].strip().lower()

                    if _id:
                        if parametro == _('r'):
                            _list = self.raids["raids"]
                            _type = _("raid")
                        elif parametro == _('q'):
                            _list = self.quests["quests"]
                            _type = _("quest")
                        else:
                            msg = await self.sender.sendMessage(_("Meowth! Invalid command!"))
                            self.delete_messages(msg)

                        obj = next((x for x in _list if int(x['id']) == int(_id)), None)
                        if obj == None:
                            msg = await self.sender.sendMessage(_("Meowth! The %s of id *%s* does not exist or has already ended!") % (_type, _id), parse_mode = "markdown")
                            self.delete_messages(msg)
                        else:
                            if command == _('/share'):
                                if obj['status'] == _('active'):
                                    if parametro == _('r'):
                                        msg = await self.sender.sendMessage(self.create_list(obj), reply_markup=self.create_keyboard(obj), parse_mode="markdown")
                                    elif parametro == _('q'):
                                        msg = await self.sender.sendMessage(self.create_quest(obj), parse_mode="markdown")

                                    if parametro == _('r'):
                                        if next((x for x in obj['messages'] if int(x['chat']['id']) == int(msg['chat']['id'])), None) != None:
                                            await self.bot.deleteMessage(telepot.message_identifier(msg))
                                            msg = await self.sender.sendMessage(_("Meowth! The %s of id *%s* has already been posted in this group!") % (_type, _id), parse_mode = "markdown")
                                            self.delete_messages(msg)

                                    if next((x for x in obj['messages'] if int(x['message_id']) == int(msg['message_id'])), None) == None:
                                        obj['messages'].append(msg)
                                        self.persist_data()
                                    else:
                                        await self.bot.deleteMessage(telepot.message_identifier(msg))
                                else:
                                    msg = await self.sender.sendMessage(_("Meowth! The raid of id *%s* has already been ended or canceled!") % (_id))
                            else:
                                add = True
                                
                                if parametro == _('r'):
                                    add = next((x for x in obj['going'] if int(x['user']['id']) == int(user['id'])), None) != None

                                if add == True:
                                    message = ""
                                    for word in params:
                                        if params.index(word) >= 2:
                                            message += f"{word.strip()} "
                                    comment = {
                                        'user': user,
                                        'comment': message
                                        }

                                    if next((x for x in obj['comments'] if int(x['user']['id']) == int(user['id'])), None) == None:
                                        obj['comments'].append(comment)
                                    else:
                                        i = 0
                                        for x in obj['comments']:
                                            if int(x['user']['id']) == int(user['id']):
                                                obj['comments'].pop(i)
                                                obj['comments'].append(comment)
                                                break
                                            else:
                                                i += 1

                                    self.persist_data()

                                    for msg in obj['messages']:
                                        if parametro == _('r'):
                                            await self.bot.editMessageText(telepot.message_identifier(msg), self.create_list(obj), reply_markup=self.create_keyboard(obj), parse_mode="markdown")
                                        else:
                                            await self.bot.editMessageText(telepot.message_identifier(msg), self.create_quest(obj), parse_mode="markdown")       
                except:
                    return
        # Help command
        elif cmd == _('/help'):
            await self.help(user_msg)
        # None of the commands
        else:
            if user['id'] != self.master and not self.is_admin(user['id']):
                await self.help(user_msg)

        # MASTER-Admins commands
        if user['id'] == self.master or self.is_admin(user['id']):
            # Visualizar Raid
            if cmd == _('/viewraid'):
                if len(params) == 1:
                   id_raid = params[0].strip()
                   if id_raid.isdigit():
                        raid = next((x for x in self.raids['raids'] if int(x['id']) == int(id_raid)), None)
                        if raid != None:
                            mensagem = self.cabecalholista(raid)
                            mensagem += self.corpolista(raid)
                            mensagem += self.create_log(raid)
                        else:
                            mensagem = "Raid de ID *%s* não existe." % (id_raid)
                   else:
                        mensagem = "Parâmetro passado não corresponde a um número."

                msg = await self.sender.sendMessage(mensagem, parse_mode="markdown")
                self.delete_messages(msg)
             # Re Ativar uma raid
            elif cmd == _('/activeraid'):
                if len(params) == 1:
                   id_raid = params[0].strip()
                   if id_raid.isdigit():
                      raid = next((x for x in self.raids['raids'] if int(x['id']) == int(id_raid)), None)
                      if raid != None and (raid['status'] == _('canceled') or raid['status'] == _('ended')):
                          raid['status'] = _('active')
                          raid['log'].append({
                              "user": user,
                              "mensagem": "Re-Ativado ás: %s" % (self.return_data_hora_local())
                          })
                          self.persist_data()
                          for mmm in raid['messages']:
                              await self.bot.editMessageText(telepot.message_identifier(mmm), self.create_list(raid),reply_markup=self.create_keyboard(raid), parse_mode="markdown")
                              message = "Raid de ID *%s* foi Reativada." % (id_raid)
                      else:
                          message = "Raid de ID *%s* ainda ativa." % (id_raid)
                   else:
                       message = "Parâmetro passado não corresponde a um número."

                msg = await self.sender.sendMessage(message, parse_mode="markdown")
                self.delete_messages(msg)

        if user_msg['chat']['type'] != 'private':
            self.delete_messages(user_msg, 1)

    async def help(self, user_msg):
        will_delete = _("\n\n_This message will be automatically deleted in a minute._") if user_msg['chat']['type'] != 'private' else ""
        admins = ""
        i = 1
        for admin_id in self.administradores:
            trainer = next((x for x in self.trainers if int(x['id']) == int(admin_id)), None)
            if trainer != None:
               if i == 1:
                   admins = ""
               elif len(self.administradores) == i:
                   admins += " ou "
               else:
                   admins += ", "
               admins += f"[{trainer['nickname']}](tg://user?id={admin_id})"
               i += 1

        msg = await self.sender.sendMessage(
        _("*Comandos*"
        "\n/treinador - Defina seu time e level."
        "\n`/treinador nickname time/cor 30`"
        "\n/level - atualiza seu nível, mas só funciona depois que o comando /treinador já tiver sido usado."
        "\n`/level 31`"
        "\n/raid - inicia uma nova raid."
        "\n`/raid pokémon,local,HH:MM`"
        "\n/editar - modifica o horário da raid."
        "\n`/editar ID_raid HH:MM`"
        "\n/editarnome - modifica o nome do pokemon da raid."
        "\n`/editarnome ID_raid nome_pokemon`"
        "\n/cancelar - cancela a raid."
        "\n`/cancelar ID_raid`"
        "\n/finalizar - finaliza uma raid."
        "\n`/finalizar ID_raid`"
        "\n/missao - criar uma missão."
        "\n`/missao tarefa,local,recompensa`"
        "\n/compartilhar - enviar uma raid ou missão para outro grupo, para que ambos sejam atualizados automaticamente nos grupos em que foram compartilhados."
        "\n`/compartilhar m/r ID_raid/ID_missao`"
        "\n/comentar - adicionar comentario na raid ou missão."
        "\n`/comentar m/r ID_raid/ID_quest comentario`"
        "\n\n*Listagem de Raid*"
        "\nPara adicionar-se à lista, basta clicar no botão Sim."
        "\nNo caso de haver mais pessoas indo com você, toque no +1 para cada treinador extra que vai com você."
        "\nCaso não consiga mais ir, clicar no Não e seu nome será removido automaticamente."
        "\n\n*Comentários*"
        "\nSomente aqueles que confirmaram que estão indo para a raid podem comentar sobre isso."
        "\nNa missão, qualquer um pode comentar."
        "\n\n*Duração da Raid*"
        "\nApós 1 hora e 45 minutos, a lista da raid é definida para terminar (hora de eclodir ovos + duração da raid)."
        "\nÀ meia-noite de cada dia, as raids e missões são apagadas."
        "\n\nQualquer dúvida, fale com %s %s") % (admins, will_delete),
        parse_mode="markdown")

        if user_msg['chat']['type'] != 'private':
            self.scheduler.event_later( 60, ('_delete_help', {'message': msg}))

    async def on___delete_bot_messages(self, event):
        await self.bot.deleteMessage(telepot.message_identifier(event['_delete_bot_messages']['delete']))

    async def on___delete_raid(self, event):
        await self.delete_data(event, self.raids['raids'], event['_delete_raid']['raid_id'])

    async def on___delete_quest(self, event):
        await self.delete_data(event, self.quests['quests'], event['_delete_quest']['quest_id'])

    async def on___delete_help(self, event):
        await self.bot.deleteMessage(telepot.message_identifier(event['_delete_help']['message']))

    async def delete_data(self, event, _list, _id):
        obj = next((x for x in _list if int(x['id']) == int(_id)), None)

        if obj != None:
            obj['status'] = _('ended')

            for msg in obj['messages']:
                if 'status' in obj:
                    await self.bot.editMessageText(telepot.message_identifier(msg), self.create_list(obj), parse_mode="markdown")
                else:
                    await self.bot.editMessageText(telepot.message_identifier(msg), self.create_quest(obj), parse_mode="markdown")

            i = 0
            for x in _list:
                if int(x['id']) == int(_id):
                    _list.pop(i)
                    self.persist_data()
                    break
                else:
                    i += 1

    async def on_callback_query(self, msg):
        query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')
        query_data = query_data.split(',')

        raid_id = query_data[0]
        response = query_data[1]
        maximum_trainers_in_raid = 20

        raid = next((x for x in self.raids['raids'] if int(x['id']) == int(raid_id)), None)
        total = self.return_total_trainers_in_raid(raid)

        if raid != None:
            user = next((x for x in raid['going'] if int(x['user']['id']) == int(msg['from']['id'])), None)

            if response == "yes":
                if user == None and total < maximum_trainers_in_raid:
                    raid['going'].append({
                        "user": msg['from'],
                        "count": 0
                    })
                else:
                    return
            elif response == "no":
                if user != None:
                    raid['going'] = self.remove(raid['going'], msg['from']['id'])
                    raid['log'].append({
                        "user": msg['from'],
                        "mensagem": 'Saiu ás: %s' % (self.return_data_hora_local())
                    })
                    i = 0
                    for comment in raid['comments']:
                        if comment['user']['id'] == msg['from']['id']:
                            raid['comments'].pop(i)
                            break
                        else:
                            i = i + 1
                else:
                    return

            else:
                if total < maximum_trainers_in_raid:
                    if user != None:
                        user['count'] += 1
                    else:
                        raid['going'].append({
                            "user": msg['from'],
                            "count": 1
                        })
                else:
                    return

            raid_keyboard = self.create_keyboard(raid)
            self.persist_data()

            for msg in raid['messages']:
                message_idf = telepot.message_identifier(msg)
                await self.bot.editMessageText(message_idf, self.create_list(raid), reply_markup=raid_keyboard, parse_mode="markdown")

    def delete_messages(self, msg, after = 5):
        self.scheduler.event_later(after, ('_delete_bot_messages', { 'delete': msg }))

    def mention_member(self, user):
        username = f"{user['first_name']}"
        if 'last_name' in user:
            username += f" {user['last_name']}"

        trainer_info = ""
        trainer = next((x for x in self.trainers if int(x['id']) == int(user['id'])), None)
        if trainer != None:
            trainer_info = f" {trainer['level']} {trainer['emoji']}"
            username = f"{trainer['nickname']}"

        return f"[{username}](tg://user?id={user['id']}){trainer_info}"

    def exists_trainer_in_raid(self,raid,iduser):
        return next((x for x in raid['going'] if int(x['user']['id']) == iduser), None) != None

    def return_data_hora_local(self):
        data_saida = datetime.datetime.now() - datetime.timedelta(hours=3)
        return data_saida.strftime('%d/%m/%Y %H:%M:%S')

    def is_admin(self, id):
        aux = False
        for admin_id in self.administradores:
            if admin_id == id:
                aux = True
                break

        return aux

    def return_total_trainers_in_raid(self, raid):
        total = len(raid['going'])
        for r in raid['going']:
            total += r['count']

        return total

    def create_keyboard(self, raid):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_('Yes'), callback_data=f"{raid['id']},yes"),
            InlineKeyboardButton(text=_('No'), callback_data=f"{raid['id']},no"),
            InlineKeyboardButton(text='+1', callback_data=f"{raid['id']},+1")]
            ])

    def create_quest(self, quest):
        message = _("#️⃣ ID: *%s*\n🕵🏽‍♂️ Quest: *%s*\n%s Place: *%s*\n%s Reward: *%s*") % (quest['id'],quest['quest'],emoji.emojize(':round_pushpin:'),quest['place'],emoji.emojize(':trophy:'),quest['reward'])

        if quest['status'] == _('active'):
            if len(quest['comments']) > 0:
                message += _("\n\n*Comments:*")
                for comment in quest['comments']:
                    message += f"\n{self.mention_member(comment['user'])}: {comment['comment']}"

            message += _("\n\n*Reported by:* %s") % (self.mention_member(quest['created_by']))
        else:
            message += f"\n\n*{quest['status'].upper()}*"

        return message

    def cabecalholista(self,raid):
        return _("#️⃣ ID: *%s*\n%s Pokémon: *%s*\n%s Place: *%s*\n%s Time: *%s*") % (raid['id'],emoji.emojize(':trident_emblem:'),raid['pokemon'],emoji.emojize(':round_pushpin:'),raid['place'],emoji.emojize(':alarm_clock:'),raid['start_time'])

    def corpolista(self,raid):
        i = 1
        message = ''
        total = self.return_total_trainers_in_raid(raid)

        if total > 0:
            message += _("\n\n*Going:* %s") % (total)

        for x in raid['going']:
            if i == 1:
                message += "\n"
            message += f"\n{i}. {self.mention_member(x['user'])}"
            i += 1

            total += x['count']

            if x['count'] > 0:
                message += f" (+{x['count']})"

        if self.return_total_trainers_in_raid(raid) == 20:
            message += _("\n\n*Lista fechada por atingir limite permitido*")

        if len(raid['comments']) > 0:
            message += _("\n\n*Comments:*")
            for comment in raid['comments']:
                message += f"\n{self.mention_member(comment['user'])}: {comment['comment']}"

        message += _("\n\n*Created by:* %s") % (self.mention_member(raid['created_by']))

        return  message

    def create_log(self,raid):
        message = _("\n\n*Log:*")
        if len(raid['log']) > 0:
            for comment in raid['log']:
                message += f"\n{self.mention_member(comment['user'])}: {comment['mensagem']}"
        else:
            message += _("\n*Não há logs para essa raid.*")

        return  message

    def create_list(self, raid):
        message = self.cabecalholista(raid)

        if raid['status'] == _('active'):
            message += self.corpolista(raid)

        else:
            message += f"\n\n*{raid['status'].upper()} POR* " + self.mention_member(raid['finish_by'])

        return message

    def remove(self, _list, id):
        i = 0
        for x in _list:
            if int(x['user']['id']) == int(id):
                _list.pop(i)
                break
            else:
                i += 1

        return _list

    def load_data(self):
        config = json.loads(open('config.json').read())

        self.master = config['master_id']
        self.administradores = config['administradores']

        self.curr_raids = json.loads(open('data/raids.json').read())
        self.pokemon = json.loads(open('data/pokemon.json').read())
        self.raids = json.loads(open('data/active_raids.json').read())
        self.trainers = json.loads(open('data/trainers.json').read())
        self.quests = json.loads(open('data/quests.json').read())

    def persist_data(self):
        # save active raids
        self.save_json(self.raids, 'data/active_raids.json')

        # save trainers
        self.save_json(self.trainers, 'data/trainers.json')

        # save quests
        self.save_json(self.quests, 'data/quests.json')

        # save current available raids
        self.save_json(self.curr_raids, 'data/raids.json')

    def save_json(self, obj, filename):
        with open(filename, 'w') as f:
            json.dump(obj, f)

    def convert_to_seconds(self, hours, minutes):
        return int((hours * 3600) + (minutes * 60))

config = json.loads(open('config.json').read())

language = gettext.translation('thepokegobot', localedir='locale', languages=[config['language']])
language.install()

bot = telepot.aio.DelegatorBot(config['token'], [
    include_callback_query_chat_id(
        pave_event_space())(
            per_chat_id(), create_open, ThePokeGOBot, timeout=600)
])

loop = asyncio.get_event_loop()
loop.create_task(MessageLoop(bot).run_forever())

print(_("Meowth! That's right!"))

loop.run_forever()
