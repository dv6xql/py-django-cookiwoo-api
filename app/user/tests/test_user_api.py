import tempfile
import os

from PIL import Image

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status


CREATE_USER_URL = reverse("user:create")
TOKEN_URL = reverse("user:token")
ME_URL = reverse("user:me")
UPLOAD_IMAGE_URL = reverse("user:upload-image")


def create_user(**params):
    """Helper function to create API user for testing purpose"""
    return get_user_model().objects.create_user(**params)


class PublicUserApiTests(TestCase):
    """Test the users API (public)"""

    def setUp(self) -> None:
        self.client = APIClient()

    def test_create_valid_user_success(self) -> None:
        """Test creating user with valid payload is successful"""
        payload = {
            "email": "test@gawlowski.com.pl",
            "password": "password1234",
            "name": "Test API User"
        }
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(**res.data)
        self.assertTrue(user.check_password(payload["password"]))
        self.assertNotIn("password", res.data)

    def test_user_exists(self) -> None:
        """Test creating user that already exists fails"""
        payload = {
            "email": "test@gawlowski.com.pl",
            "password": "password1234",
            "name": "Test API User"
        }
        create_user(**payload)

        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_too_short(self) -> None:
        """Test that the password must be more than 12 characters"""
        payload = {
            "email": "test@gawlowski.com.pl",
            "password": "password",
            "name": "Test API User"
        }
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        user_exists = get_user_model().objects.filter(
            email=payload["email"]
        ).exists()
        self.assertFalse(user_exists)

    def test_create_token_for_api_user(self) -> None:
        """Test that a token is created for the API user"""
        payload = {
            "email": "test@gawlowski.com.pl",
            "password": "password1234",
            "name": "Test API User"
        }
        create_user(**payload)
        res = self.client.post(TOKEN_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("token", res.data)

    def test_create_token_invalid_credentials(self) -> None:
        """Test that token is not created if invalid credentials are given"""
        payload = {
            "email": "test@gawlowski.com.pl",
            "password": "password1234",
            "name": "Test API User"
        }
        create_user(**payload)
        payload["password"] = "invalidpassword"
        res = self.client.post(TOKEN_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("token", res.data)

    def test_create_token_no_user(self) -> None:
        """Test that token is not created if user does not exist"""
        payload = {
            "email": "test@gawlowski.com.pl",
            "password": "password1234",
            "name": "Test API User"
        }
        res = self.client.post(TOKEN_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("token", res.data)

    def test_create_token_missing_email_field(self) -> None:
        """Test that email is required"""
        payload = {
            "email": "",
            "password": "password1234",
            "name": "Test API User"
        }
        res = self.client.post(TOKEN_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("token", res.data)

    def test_create_token_missing_password_field(self) -> None:
        """Test that password is required"""
        payload = {
            "email": "test@gawlowski.com.pl",
            "password": "",
            "name": "Test API User"
        }
        res = self.client.post(TOKEN_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("token", res.data)

    def test_retrieve_user_unauthorized(self) -> None:
        """Test that authentication is required for users"""
        res = self.client.get(ME_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateUserApiTests(TestCase):
    """Test API requests that require authentication"""

    def setUp(self) -> None:
        payload = {
            "email": "test@gawlowski.com.pl",
            "password": "password1234",
            "name": "Test API User"
        }
        self.user = create_user(**payload)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_profile_success(self) -> None:
        """Test retrieving profile for logged in used"""
        res = self.client.get(ME_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {
            "name": self.user.name,
            "email": self.user.email,
            "image": ""
        })
        self.assertNotIn("password", res.data)

    def test_post_me_not_allowed(self) -> None:
        """Test that POST is not allowed on the ME url"""
        res = self.client.post(ME_URL, {})

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_update_user_profile(self) -> None:
        """Test updating the user profile for authenticated user"""
        payload = {
            "email": "newtest@gawlowski.com.pl",
            "password": "newpassword1234",
            "name": "New Test API User"
        }

        res = self.client.patch(ME_URL, payload)

        self.user.refresh_from_db()
        self.assertEqual(self.user.name, payload["name"])
        self.assertTrue(self.user.check_password(payload["password"]))
        self.assertEqual(self.user.email, payload["email"])
        self.assertEqual(res.status_code, status.HTTP_200_OK)


class UserImageUploadTests(TestCase):
    """Test API request for uploading user image"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = get_user_model().objects.create(
            email="test@gawlowski.com.pl",
            password="password1234"
        )
        self.client.force_authenticate(self.user)

    def tearDown(self) -> None:
        self.user.image.delete()

    def test_upload_user_image(self) -> None:
        """Test uploading a user image"""
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)

            payload = {
                "image": ntf
            }
            res = self.client.post(UPLOAD_IMAGE_URL,
                                   payload,
                                   format="multipart")

            self.user.refresh_from_db()
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertIn("image", res.data)
            self.assertTrue(os.path.exists(self.user.image.path))

    def test_upload_user_image_bad_request(self) -> None:
        """Test uploading an invalid user image"""
        payload = {
            "image": "invalid"
        }
        res = self.client.post(UPLOAD_IMAGE_URL, payload, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_profile_with_image_success(self) -> None:
        """Test retrieving profile with user image for logged-in user"""
        self.test_upload_user_image()
        res = self.client.get(ME_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("image", res.data)
        self.assertNotEqual("", self.user.image.path)
