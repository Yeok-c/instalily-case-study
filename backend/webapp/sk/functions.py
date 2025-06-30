from semantic_kernel.functions import kernel_function

class OrderPizzaPlugin:
    def __init__(self, pizza_service, user_context, payment_service):
        self.pizza_service = pizza_service
        self.user_context = user_context
        self.payment_service = payment_service

    @kernel_function
    async def get_pizza_menu(self):
        return await self.pizza_service.get_menu()

    @kernel_function(
        description="Add a pizza to the user's cart; returns the new item and updated cart"
    )
    async def add_pizza_to_cart(self, size: PizzaSize, toppings: List[PizzaToppings], quantity: int = 1, special_instructions: str = ""):
        cart_id = await self.user_context.get_cart_id()
        return await self.pizza_service.add_pizza_to_cart(cart_id, size, toppings, quantity, special_instructions)

    @kernel_function(
        description="Remove a pizza from the user's cart; returns the updated cart"
    )
    async def remove_pizza_from_cart(self, pizza_id: int):
        cart_id = await self.user_context.get_cart_id()
        return await self.pizza_service.remove_pizza_from_cart(cart_id, pizza_id)

    @kernel_function(
        description="Returns the specific details of a pizza in the user's cart; use this instead of relying on previous messages since the cart may have changed since then."
    )
    async def get_pizza_from_cart(self, pizza_id: int):
        cart_id = await self.user_context.get_cart_id()
        return await self.pizza_service.get_pizza_from_cart(cart_id, pizza_id)

    @kernel_function(
        description="Returns the user's current cart, including the total price and items in the cart."
    )
    async def get_cart(self):
        cart_id = await self.user_context.get_cart_id()
        return await self.pizza_service.get_cart(cart_id)

    @kernel_function(
        description="Checkouts the user's cart; this function will retrieve the payment from the user and complete the order."
    )
    async def checkout(self):
        cart_id = await self.user_context.get_cart_id()
        payment_id = await self.payment_service.request_payment_from_user(cart_id)
        return await self.pizza_service.checkout(cart_id, payment_id)