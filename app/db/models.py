from datetime import datetime
from typing import Optional, List
import json

from aiogram import types
from tortoise.models import Model
from tortoise import fields, exceptions


class User(Model):
    class Meta:
        table = "users"
        table_description = "Users"
        ordering = ["id"]

    id: int = fields.BigIntField(pk=True)
    telegram_id: int = fields.BigIntField(unique=True)
    username: str = fields.CharField(max_length=64)
    full_name: str = fields.CharField(max_length=128)
    is_blocked: bool = fields.BooleanField(default=False)
    block_reason: str = fields.TextField(null=True)
    tos_agreement: bool = fields.BooleanField(default=False)
    referral_param: str = fields.CharField(max_length=100, null=True)

    @classmethod
    async def add_user(cls, user: types.User) -> Optional["User"]:
        try:
            db_user = await cls.create(
                telegram_id=user.id,
                username=user.username,
                full_name=user.full_name
            )
        except exceptions.IntegrityError:
            return None

        return db_user

    @classmethod
    async def get_user(cls, telegram_id: int) -> Optional["User"]:
        return await cls.get_or_none(telegram_id=telegram_id)

    @classmethod
    async def get_by_username(cls, username: str):

        records = await cls.filter(username=username).order_by('id')
        
        if len(records) > 1:
            for record in records[:-1]:
                await record.delete()
            return records[-1]
        elif records:
            return records[0]
        return None

class Implementer(Model):
    class Meta:
        table = "implementers"
        table_description = "Implementers"
        ordering = ["id"]

    id: int = fields.BigIntField(pk=True)
    user: User = fields.ForeignKeyField("models.User", related_name="implementer")
    full_name: str = fields.CharField(max_length=128)
    mark: str = fields.CharField(max_length=128, null=True)
    date_birth: datetime = fields.DatetimeField()
    phone_number: str = fields.CharField(max_length=64, unique=True)
    nationality: bool = fields.BooleanField(default=True)
    bots: fields.ManyToManyRelation["Bot"]
    towns: fields.ManyToManyRelation["Town"]
    requests: fields.ManyToManyRelation["Request"]
    success_requests: int = fields.IntField(default=0)
    fail_requests: int = fields.IntField(default=0)
    youdo_id: int = fields.IntField(null=True)
    priority_group: int = fields.IntField(default=0)
    rating: int = fields.IntField(default=0)
    tools = fields.JSONField(null=True)
    employment_type = fields.CharField(max_length=64, default='contract')

    inn: str = fields.CharField(max_length=128, null=True)
    passport: str = fields.CharField(max_length=128, null=True)

    @property
    def national(self):
        if self.nationality:
            return 'Да'

        return 'Нет'

    @classmethod
    async def add_implementer(cls, user: User, full_name: str, date_birth: datetime,
                              phone_number: str,
                              nationality: bool,
                              tools: bool,
                              straps: bool,
    ) -> Optional["Implementer"]:
        tools_jsonb = {}
    
        if tools:
            tools_jsonb.update({"tools": tools})
        if straps:
            tools_jsonb.update({"straps": straps})
        implementer = await cls.create(
            user=user,
            full_name=full_name,
            date_birth=date_birth,
            phone_number=phone_number,
            nationality=nationality,
            mark='Нет',
            tools=json.dumps(tools_jsonb) if tools_jsonb else None  
        )
        return implementer

    @classmethod
    async def get_implementer(cls, user: User, prefetch_related: bool = True) -> Optional["Implementer"]:
        if prefetch_related:
            return await cls.get_or_none(user=user).prefetch_related("bots")
        else:
            return await cls.get_or_none(user=user)

    @classmethod
    async def get_phone_number(cls, phone_number: str) -> Optional["Implementer"]:
        return await cls.get_or_none(phone_number=phone_number)

    @classmethod
    async def get_by_id(cls, implementer_id: int, prefetch_related: bool = True):
        if prefetch_related:
            return await cls.get_or_none(id=implementer_id).prefetch_related("user")
        else:
            return await cls.get_or_none(id=implementer_id)


class Operator(Model):
    class Meta:
        table = "operators"
        table_description = "Operators"
        ordering = ["id"]

    id: int = fields.BigIntField(pk=True)
    user: User = fields.ForeignKeyField("models.User", related_name="operator")
    requests: fields.ReverseRelation["Request"]
    priority_stats = fields.JSONField(null=True)
    seal = fields.BooleanField(default=False)
    seal_count = fields.IntField(default=0)
    seal_manual = fields.BooleanField(default=False)

    @classmethod
    async def add_operator(cls, user: User) -> Optional["Operator"]:
        operator = await cls.create(
            user=user
        )
        return operator

    @classmethod
    async def get_operator(cls, user: User, prefetch_related: bool = True) -> Optional["Operator"]:
        if prefetch_related:
            return await cls.get_or_none(user=user).prefetch_related("user")
        else:
            return await cls.get_or_none(user=user)

    @classmethod
    async def get_by_id(cls, operator_id: int, prefetch_related: bool = True):
        if prefetch_related:
            return await cls.get_or_none(id=operator_id).prefetch_related("user")
        else:
            return await cls.get_or_none(id=operator_id)

    @classmethod
    async def get_all(cls, prefetch_related: bool = True) -> List["Operator"]:
        if prefetch_related:
            return await cls.all().prefetch_related("user")
        else:
            return await cls.all()


class Bot(Model):
    class Meta:
        table = "bots"
        table_description = "Bots"
        ordering = ["id"]

    id: int = fields.BigIntField(pk=True)
    token: str = fields.CharField(max_length=128, unique=True)
    username: str = fields.CharField(max_length=64, unique=True)
    title: str = fields.CharField(max_length=128)
    city: str = fields.CharField(max_length=128, unique=True)
    state: str = fields.CharField(max_length=128, null=True)
    implementers: fields.ManyToManyRelation[Implementer] = fields.ManyToManyField("models.Implementer",
                                                                                  related_name="bots")
    towns: fields.ReverseRelation["Town"]
    status: bool = fields.BooleanField(default=True)

    @classmethod
    async def add_bot(cls, token: str, city: str, username: str, title: str,
                      state: str = None) -> Optional["Bot"]:
        try:
            bot = await cls.create(
                token=token,
                city=city,
                state=state,
                username=username,
                title=title
            )
            return bot

        except exceptions.IntegrityError:
            return None

    @classmethod
    async def get_all(cls, prefetch_related: bool = True) -> List["Bot"]:
        if prefetch_related:
            return await cls.filter(status=True).all().prefetch_related("implementers", "towns")
        else:
            return await cls.filter(status=True).all()

    @classmethod
    async def get_by_id(cls, bot_id: int, prefetch_related: bool = True) -> Optional["Bot"]:
        if prefetch_related:
            return await cls.get_or_none(id=bot_id).prefetch_related("implementers", "implementers__user", "towns")
        else:
            return await cls.get_or_none(id=bot_id)

    @classmethod
    async def get_by_id_prefetched_towns(cls, bot_id: int) -> Optional["Bot"]:
        return await cls.get_or_none(id=bot_id).prefetch_related("towns")

    @classmethod
    async def get_by_city(cls, city: str, prefetch_related: bool = True) -> Optional["Bot"]:
        if prefetch_related:
            return await cls.filter(city=city).first().prefetch_related("implementers", "towns")
        else:
            return await cls.filter(city=city).first()

    @classmethod
    async def get_all_bots(cls, prefetch_related: bool = True) -> List["Bot"]:
        if prefetch_related:
            return await cls.filter().all().prefetch_related("implementers", "towns")
        else:
            return await cls.filter().all()

    @classmethod
    async def get_by_state(cls, state: str, prefetch_related: bool = True):
        if prefetch_related:
            return await cls.filter(state=state, status=True).all().prefetch_related("implementers", "towns")
        else:
            return await cls.filter(state=state, status=True).all()

    @classmethod
    async def get_by_token(cls, token: str, prefetch_related: bool = True):
        if prefetch_related:
            return await cls.get_or_none(token=token).prefetch_related("implementers", "towns")
        else:
            return await cls.get_or_none(token=token)


class Town(Model):
    class Meta:
        table = "towns"
        table_description = "Towns"
        ordering = ["id"]

    id: int = fields.BigIntField(pk=True)
    name: str = fields.CharField(max_length=128)
    bot: Bot = fields.ForeignKeyField("models.Bot", related_name="towns")
    implementers: fields.ManyToManyRelation[Implementer] = fields.ManyToManyField("models.Implementer",
                                                                                  related_name="towns")

    @classmethod
    async def add_town(cls, name: str, bot: Bot) -> Optional["Town"]:
        try:
            town = await cls.create(
                name=name,
                bot=bot
            )
            return town

        except exceptions.IntegrityError:
            return None

    @classmethod
    async def get_by_id(cls, town_id: int, prefetch_related: bool = True) -> Optional["Town"]:
        if prefetch_related:
            return await cls.get_or_none(id=town_id).prefetch_related("implementers", "implementers__user", "bot")
        else:
            return await cls.get_or_none(id=town_id)


class OperatorInvite(Model):
    class Meta:
        table = "operator_invites"
        table_description = "Operator invites"
        ordering = ["id"]

    id: int = fields.BigIntField(pk=True)
    user: User = fields.ForeignKeyField("models.User", related_name="operator_requests")
    is_accepted: bool = fields.BooleanField(default=False)

    @classmethod
    async def add_request(cls, user: User) -> Optional["OperatorInvite"]:
        try:
            request = await cls.create(
                user=user
            )
            return request

        except exceptions.IntegrityError:
            return None

    @classmethod
    async def get_by_id(cls, request_id, prefetch_related: bool = True) -> Optional["OperatorInvite"]:
        if prefetch_related:
            return await cls.get_or_none(id=request_id).prefetch_related("user")
        else:
            return await cls.get_or_none(id=request_id)


class Request(Model):
    class Meta:
        table = "requests"
        table_description = "Requests"
        ordering = ["-id"]

    id: int = fields.BigIntField(pk=True)
    operator: Operator = fields.ForeignKeyField("models.Operator", related_name="requests")
    implementers: fields.ManyToManyRelation[Implementer] = fields.ManyToManyField("models.Implementer",
                                                                                  related_name="requests")
    town_id: int = fields.IntField(null=True)
    city_id: int = fields.IntField(null=True)
    order_id: int = fields.CharField(max_length=32)
    date: str = fields.CharField(max_length=128)
    people: int = fields.IntField(max_length=128)
    metro: str = fields.CharField(max_length=128, null=True)
    address_street: str = fields.CharField(max_length=128)
    address_number: str = fields.CharField(max_length=128)
    address_lat: float = fields.FloatField()
    address_lon: float = fields.FloatField()
    national: str = fields.CharField(max_length=16, null=True)
    comment: str = fields.CharField(max_length=512)
    shift_description: str = fields.CharField(max_length=256, null=True)
    price_hour: str = fields.CharField(max_length=128)
    price_state: str = fields.CharField(max_length=128,default='0')
    price_regular: str = fields.CharField(max_length=128,default='0')
    min_time: str = fields.CharField(max_length=128)
    is_active: bool = fields.BooleanField(default=True)
    is_completed: bool = fields.BooleanField(default=False)
    is_canceled: bool = fields.BooleanField(default=False)

    @classmethod
    async def add_request(cls, operator: Operator, date: str, people: str, address_street: str, address_number: str,
                          address_lat: float, address_lon: float, comment: str,price_regular: str, price_state: str, price_hour: str, min_time: str,
                          order_id: str, national: str, town_id: int = None, city_id: int = None, shift_description: str = None,
                          metro: str = None) -> Optional["Request"]:
        if national == 'every':
            national = None
        try:
            request = await cls.create(
                operator=operator,
                order_id=order_id,
                date=date,
                people=people,
                national=national,
                address_street=address_street,
                address_number=address_number,
                address_lat=address_lat,
                address_lon=address_lon,
                comment=comment,
                shift_description=shift_description,
                price_regular=price_regular,
                price_state=price_state,
                price_hour=price_hour,
                min_time=min_time,
                town_id=town_id,
                city_id=city_id,
                metro=metro
            )
            return request

        except exceptions.IntegrityError:
            return None

        except exceptions.ValidationError:
            return None

    @classmethod
    async def get_by_id(cls, request_id: int, prefetch_related: bool = True) -> Optional["Request"]:
        if prefetch_related:
            return await cls.get_or_none(id=request_id).prefetch_related("operator", "operator__user", "implementers",
                                                                         "implementers__user")
        else:
            return await cls.get_or_none(id=request_id)

    @classmethod
    async def get_by_operator(cls,
                              operator: Operator,
                              is_active: bool = None,
                              is_finish: bool = None,
                              prefetch_related: bool = True) -> List["Request"]:
        if is_active is None:
            query = cls.filter(operator=operator).all()
        elif is_finish is True:
            query = cls.filter(operator=operator, is_canceled=False,
                               is_completed=is_finish).all()
        else:
            query = cls.filter(operator=operator, is_active=is_active,
                               is_completed=is_finish, is_canceled=False).all()

        if prefetch_related:
            return await query.prefetch_related("implementers")
        else:
            return await query

    @classmethod
    async def get_user_active_requests(cls, implementer: Implementer):
        return await cls.filter(
            implementers__id=implementer.id,
            is_active=True,
            is_completed=False,
            is_canceled=False
        ).all()

    @classmethod
    async def get_user_actual_requests(cls, implementer: Implementer):
        return await cls.filter(
            implementers__id=implementer.id,
            is_completed=False,
            is_canceled=False
        ).all()

    @classmethod
    async def get_finish_requests(cls, operator: Operator, prefetch_related: bool = True) -> List["Request"]:
        if prefetch_related:
            return await cls.filter(operator=operator, is_completed=True, is_active=True).all().prefetch_related(
                "implementers")
        else:
            return await cls.filter(operator=operator, is_completed=True, is_active=True).all()

    @classmethod
    async def get_user_finish_requests_count(cls, user: User) -> int:
        return await cls.filter(implementers__user=user, is_completed=True, is_active=True).count()

    @classmethod
    async def get_all(cls, prefetch_related: bool = True) -> List["Request"]:
        if prefetch_related:
            return await cls.all().prefetch_related("operator", "implementers")
        else:
            return await cls.all()


    @classmethod
    async def get_by_order_id(cls, order_id: str, prefetch_related: bool = True) -> List["Request"]:
        if prefetch_related:
            return await cls.filter(order_id=order_id).all().prefetch_related("operator", "implementers")
        else:
            return await cls.filter(order_id=order_id).all()


class ImplementerRequests(Model):
    class Meta:
        table = "implementer_requests"
        table_description = "Implementer requests"
        ordering = ["id"]

    id: int = fields.BigIntField(pk=True)
    implementers_ids: List[int] = fields.JSONField(default=[])
    request_id: int = fields.IntField(null=True)
    accepted: bool = fields.BooleanField(default=False)

    @classmethod
    async def add_request(cls, implementers_ids: List[int], request_id: int = None) -> Optional["ImplementerRequests"]:
        try:
            request = await cls.create(
                implementers_ids=implementers_ids,
                request_id=request_id
            )
            return request

        except exceptions.IntegrityError:
            return None

    @classmethod
    async def get_by_id(cls, request_id: int) -> Optional["ImplementerRequests"]:
        return await cls.get_or_none(id=request_id)

    @classmethod
    async def get_by_request_id(cls, request_id: int) -> Optional["ImplementerRequests"]:
        return await cls.get_or_none(request_id=request_id)

class ChatMessages(Model):
    class Meta:
        table = "chat_messages"
        table_description = "Chat Messages"

    request: int = fields.BigIntField(null=False)
    message_ids = fields.JSONField(default=[])

class Order(Model):
    id = fields.IntField(pk=True)  
    order_id = fields.CharField(max_length=50, unique=True)  
    data = fields.JSONField()  

    class Meta:
        table = "orders"  

class Referral(Model):
    param = fields.CharField(max_length=100, unique=True)
    counter = fields.IntField(default=0)

    class Meta:
        table = "referrals"
    
    @classmethod
    async def increment_counter(cls, param):
        referral, created = await cls.get_or_create(param=param)
        referral.counter += 1
        await referral.save()