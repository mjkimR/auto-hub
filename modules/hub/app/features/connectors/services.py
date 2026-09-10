import uuid
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from app.features.connectors.crypto import ConnectorCredentialCipher, EncryptedCredentials
from app.features.connectors.models import Connector
from app.features.connectors.repos import ConnectorRepository
from app.features.connectors.schemas import ConnectorCreate, ConnectorPatch, ConnectorPut
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from app_layer_base.base.services.exists_check_hook import ExistsCheckHook
from app_layer_base.base.services.hooks import Operation
from app_layer_base.base.services.unique_constraints_hook import UniqueConstraintHook
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import ColumnElement


class ConnectorContextKwargs(BaseContextKwargs):
    pass


class ConnectorUniqueHook(UniqueConstraintHook[Connector, ConnectorContextKwargs]):
    async def constraints(
        self,
        op: Operation[ConnectorContextKwargs],
        data: BaseModel,
    ) -> AsyncIterator[tuple[ColumnElement[bool], str]]:
        name = getattr(data, "name", None)
        if name:
            yield Connector.name == name, "Connector name must be unique."


class ConnectorService(
    BaseCreateServiceMixin[ConnectorRepository, Connector, ConnectorCreate, ConnectorContextKwargs],
    BaseGetMultiServiceMixin[ConnectorRepository, Connector, ConnectorContextKwargs],
    BaseGetServiceMixin[ConnectorRepository, Connector, ConnectorContextKwargs],
    BaseUpdateServiceMixin[
        ConnectorRepository,
        Connector,
        ConnectorPut,
        ConnectorPatch,
        ConnectorContextKwargs,
    ],
    BaseDeleteServiceMixin[ConnectorRepository, Connector, ConnectorContextKwargs],
):
    def __init__(
        self,
        repo: Annotated[ConnectorRepository, Depends()],
        cipher: Annotated[ConnectorCredentialCipher, Depends()],
    ):
        self._repo = repo
        self._cipher = cipher
        self.hooks = (ConnectorUniqueHook(), ExistsCheckHook())

    @property
    def repo(self) -> ConnectorRepository:
        return self._repo

    @property
    def context_model(self):
        return ConnectorContextKwargs

    async def create(
        self,
        session: AsyncSession,
        obj_data: ConnectorCreate,
        context: ConnectorContextKwargs | None = None,
        **update_fields,
    ) -> Connector:
        connector_id = uuid.uuid4()
        encrypted = await self._cipher.encrypt(connector_id, obj_data.provider.value, obj_data.credentials)
        return await super().create(
            session,
            obj_data,
            context=context,
            id=connector_id,
            credentials_ciphertext=encrypted.ciphertext,
            credentials_nonce=encrypted.nonce,
            credential_key_version=encrypted.key_version,
            **update_fields,
        )

    async def put(
        self,
        session: AsyncSession,
        obj_pk: UUID,
        obj_data: ConnectorPut,
        context: ConnectorContextKwargs | None = None,
        **update_fields,
    ) -> Connector | None:
        encrypted = await self._cipher.encrypt(obj_pk, obj_data.provider.value, obj_data.credentials)
        return await super().put(
            session,
            obj_pk,
            obj_data,
            context=context,
            **self._encrypted_fields(encrypted),
            **update_fields,
        )

    async def patch(
        self,
        session: AsyncSession,
        obj_pk: UUID,
        obj_data: ConnectorPatch,
        context: ConnectorContextKwargs | None = None,
        **update_fields,
    ) -> Connector | None:
        if "credentials" in obj_data.model_fields_set:
            connector = await self.repo.get_by_pk(session, obj_pk)
            if connector is not None:
                encrypted = await self._cipher.encrypt(obj_pk, connector.provider, obj_data.credentials)
                update_fields.update(self._encrypted_fields(encrypted))
        return await super().patch(session, obj_pk, obj_data, context=context, **update_fields)

    async def get_credentials(self, session: AsyncSession, connector: Connector) -> dict:
        return await self._cipher.decrypt(
            connector.id,
            connector.provider,
            EncryptedCredentials(
                ciphertext=connector.credentials_ciphertext,
                nonce=connector.credentials_nonce,
                key_version=connector.credential_key_version,
            ),
        )

    @staticmethod
    def _encrypted_fields(encrypted: EncryptedCredentials) -> dict:
        return {
            "credentials_ciphertext": encrypted.ciphertext,
            "credentials_nonce": encrypted.nonce,
            "credential_key_version": encrypted.key_version,
        }
