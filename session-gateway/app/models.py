"""
Modelos de LEITURA do Session Gateway.

Decisão: em vez de importar app.models do core-api (o que acoplaria os
dois serviços no nível de código Python, exigindo que ambos sejam
deployados/versionados juntos), o Session Gateway define sua PRÓPRIA
visão mínima e somente-leitura das tabelas de que precisa. Isso é o
padrão comum em arquiteturas de microsserviços: cada serviço enxerga só
o subconjunto de colunas que realmente usa, e uma migração de schema no
core-api que não toque essas colunas específicas não quebra o gateway.

O enum `status` do core-api (LabInstanceStatus) é armazenado no banco
como o NOME do membro do enum Python (ex: "RUNNING"), não como o valor
minúsculo — por isso comparamos com a string literal "RUNNING" em vez
de duplicar o enum aqui.
"""
from sqlalchemy import Column, DateTime, JSON, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

STATUS_RUNNING = "RUNNING"


class LabInstance(Base):
    __tablename__ = "lab_instances"

    id = Column(String, primary_key=True)
    lab_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    network_namespace = Column(String, nullable=True)
    container_id = Column(String, nullable=True)
    access_token = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)


class Lab(Base):
    __tablename__ = "labs"

    id = Column(String, primary_key=True)
    definition = Column(JSON, nullable=False)
