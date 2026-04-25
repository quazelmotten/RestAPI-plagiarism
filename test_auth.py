import asyncio

from auth.service import AuthService


async def test():
    print("Testing AuthService.get_user_by_email('test3@example.com')")
    user = await AuthService.get_user_by_email('test3@example.com')
    print(f"User found: {user}")
    if user:
        print(f"User email: {user.email}, user hashed password: {user.hashed_password}")

    print("\nTesting AuthService.authenticate_user('test3@example.com', 'Test123456!')")
    auth_user = await AuthService.authenticate_user('test3@example.com', 'Test123456!')
    print(f"Authenticated user: {auth_user}")

if __name__ == "__main__":
    asyncio.run(test())
