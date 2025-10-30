from __future__ import annotations

import factory
from factory.alchemy import SQLAlchemyModelFactory

from app import models
from app.security.authentication import hash_password


class BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session_persistence = "flush"


class UserFactory(BaseFactory):
    class Meta:
        model = models.User

    email = factory.Sequence(lambda index: f"user{index}@example.com")
    full_name = factory.Faker("name")
    role = models.UserRole.OPERATOR
    is_active = True
    default_workspace = "dev"

    @factory.post_generation
    def plain_password(self, create, extracted, **kwargs):
        password = extracted or "Password123!"
        self.hashed_password = hash_password(password)
