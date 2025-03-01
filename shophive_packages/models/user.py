from flask_login import UserMixin  # type: ignore
from flask_bcrypt import (  # type: ignore
    generate_password_hash, check_password_hash)
from shophive_packages import db
from shophive_packages.models.product import Product
from typing import List, TYPE_CHECKING, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime
from datetime import datetime
from shophive_packages.models.types import BaseQuery

if TYPE_CHECKING:
    from shophive_packages.models.cart import Cart
    from shophive_packages.models.orders import Order, OrderItem
else:
    from shophive_packages.models.cart import Cart


class BaseUser(db.Model):  # type: ignore[name-defined]
    """Base user class with common functionality."""
    __abstract__ = True
    __allow_unmapped__ = True

    query: BaseQuery

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        nullable=False
    )
    password: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    def set_password(self, password: str) -> None:
        """Hash and set the user's password"""
        if password:
            self.password = generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str) -> bool:
        """Check if provided password matches hash"""
        if not self.password:
            return False
        return bool(check_password_hash(self.password, password))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.username}>"


class User(BaseUser, UserMixin):  # Changed to inherit from BaseUser
    """User model representing buyers in the system."""
    __tablename__ = 'user'
    __allow_unmapped__ = True  # Allow unmapped attributes

    # Define columns first
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        nullable=False
    )
    password: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )
    type: Mapped[str] = mapped_column(
        String(50)
    )
    role: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="buyer"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=db.func.now(),
        nullable=False
    )

    __mapper_args__ = {
        'polymorphic_on': type,
        'polymorphic_identity': 'user'
    }

    # Relationships
    orders: Mapped[List['Order']] = relationship(
        "Order",
        back_populates="buyer",
        lazy="select"
    )
    products: Mapped[List['Product']] = relationship(
        "Product",
        foreign_keys='Product.seller_id',
        back_populates="seller",
        lazy="select"
    )
    carts: Mapped[List['Cart']] = relationship(
        "Cart",
        back_populates="user",
        lazy=True
    )

    # Remove the direct query assignment
    # Instead, let SQLAlchemy handle it through the metaclass
    query_class = BaseQuery

    def __init__(
        self,
        username: str,
        email: str,
        password: Optional[str] = None,
        role: str = "buyer"
    ) -> None:
        super().__init__()  # Call BaseUser's __init__
        self.username = username
        self.email = email
        self.role = role
        if password:
            self.set_password(password)

    def get_cart(self) -> List[Cart]:
        """Get user's cart items"""
        from typing import cast
        return cast(List[Cart], Cart.query.filter_by(user_id=self.id).all())

    def add_to_cart(self, product: Product, quantity: int = 1) -> None:
        """Add item to user's cart"""
        cart_item = Cart.query.filter_by(
            user_id=self.id,
            product_id=product.id
        ).first()

        try:
            if cart_item:
                cart_item.quantity += quantity
            else:
                cart_item = Cart(
                    user_id=self.id,
                    product_id=product.id,
                    quantity=quantity
                )
                db.session.add(cart_item)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    def get_cart_total(self) -> float:
        """Calculate total price of cart items"""
        try:
            total = sum(
                float(item.product.price * item.quantity)
                for item in self.get_cart()
            )
            return total
        except Exception:
            return 0.0

    def check_password(self, password: str) -> bool:
        """Check if provided password matches stored hash."""
        if not self.password:
            return False
        return bool(check_password_hash(self.password, password))

    def get_id(self) -> str:
        """Return user ID with type prefix."""
        if isinstance(self, Seller):
            return f"seller_{self.id}"
        return f"user_{self.id}"


class Seller(User):
    """Seller model extending the User model."""
    __tablename__ = 'seller'
    __allow_unmapped__ = True

    id: Mapped[int] = mapped_column(
        db.ForeignKey('user.id'),
        primary_key=True
    )

    __mapper_args__ = {
        'polymorphic_identity': 'seller',
        'inherit_condition': (id == User.id)
    }

    # Keep only Seller-specific relationships and attributes
    orders: Mapped[List['OrderItem']] = relationship(
        "OrderItem",
        back_populates="seller",
        lazy="select"
    )

    def __init__(
        self, username: str, email: str, password: Optional[str] = None
    ) -> None:
        super().__init__(username, email, password, role="seller")

    def get_id(self) -> str:
        """Required by Flask-Login"""
        return f"seller_{self.id}"
