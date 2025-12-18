# main/repository/userRepository.py
from django.contrib.auth.models import User
from django.db.models import Q, QuerySet
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository para operaciones de acceso a datos de usuarios"""

    @staticmethod
    def get_all(order_by: str = '-date_joined') -> QuerySet:
        """Obtiene todos los usuarios"""
        return User.objects.all().order_by(order_by)

    @staticmethod
    def get_by_id(user_id: int) -> Optional[User]:
        """Obtiene un usuario por ID"""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.warning(f'Usuario con ID {user_id} no encontrado')
            return None

    @staticmethod
    def filter_by_search(queryset: QuerySet, search_term: str) -> QuerySet:
        """Filtra usuarios por término de búsqueda"""
        return queryset.filter(
            Q(username__icontains=search_term) |
            Q(email__icontains=search_term) |
            Q(first_name__icontains=search_term) |
            Q(last_name__icontains=search_term)
        )

    @staticmethod
    def filter_by_status(queryset: QuerySet, is_active: bool) -> QuerySet:
        """Filtra usuarios por estado"""
        return queryset.filter(is_active=is_active)

    @staticmethod
    def filter_by_role(queryset: QuerySet, role: str) -> QuerySet:
        """Filtra usuarios por rol"""
        if role == 'superuser':
            return queryset.filter(is_superuser=True)
        elif role == 'staff':
            return queryset.filter(is_staff=True, is_superuser=False)
        elif role == 'regular':
            return queryset.filter(is_staff=False, is_superuser=False)
        return queryset

    @staticmethod
    def count_all() -> int:
        """Cuenta total de usuarios"""
        return User.objects.count()

    @staticmethod
    def count_active() -> int:
        """Cuenta usuarios activos"""
        return User.objects.filter(is_active=True).count()

    @staticmethod
    def count_superusers() -> int:
        """Cuenta superusuarios"""
        return User.objects.filter(is_superuser=True).count()

    @staticmethod
    def count_staff() -> int:
        """Cuenta usuarios staff"""
        return User.objects.filter(is_staff=True).count()

    @staticmethod
    def exists_by_username(username: str, exclude_id: Optional[int] = None) -> bool:
        """Verifica si existe un usuario con el username"""
        queryset = User.objects.filter(username=username)
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        return queryset.exists()

    @staticmethod
    def exists_by_email(email: str, exclude_id: Optional[int] = None) -> bool:
        """Verifica si existe un usuario con el email"""
        queryset = User.objects.filter(email=email)
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        return queryset.exists()

    @staticmethod
    def create(username: str, email: str, password: str, first_name: str = '',
               last_name: str = '', is_active: bool = True, is_staff: bool = False,
               is_superuser: bool = False) -> User:
        """Crea un nuevo usuario"""
        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
            is_staff=is_staff,
            is_superuser=is_superuser,
        )
        user.set_password(password)
        user.save()
        logger.info(f'Usuario creado: {username}')
        return user

    @staticmethod
    def update(user: User, **kwargs) -> User:
        """Actualiza un usuario"""
        for key, value in kwargs.items():
            if key == 'password' and value:
                user.set_password(value)
            elif value is not None and hasattr(user, key):
                setattr(user, key, value)
        user.save()
        logger.info(f'Usuario actualizado: {user.username}')
        return user

    @staticmethod
    def delete(user: User) -> str:
        """Elimina un usuario"""
        username = user.username
        user.delete()
        logger.info(f'Usuario eliminado: {username}')
        return username