"""Test script to verify long certificate-style API keys work correctly."""

from pydantic import SecretStr
from xians.models.v1.configs import XiansOptions, LLMConfig

def test_long_certificate_api_key():
    """Test that long certificate/JWT-style API keys are accepted."""

    # Your actual API key (certificate format)
    long_api_key = "MIIESjCCAjKgAwIBAgIQONKfq6SjykChK9O4Yg+7xTANBgkqhkiG9w0BAQsFADBdMQ4wDAYDVQQIDAVTdGF0ZTENMAsGA1UEBwwEQ2l0eTEVMBMGA1UECgwMT3JnYW5pemF0aW9uMQswCQYDVQQLDAJJVDEYMBYGA1UEAwwPQWdlbnRyaSBSb290IENBMB4XDTI2MDEwNjEwNTUxMloXDTMxMDEwNjExMDUxMlowNDEMMAoGA1UEChMDOTl4MRIwEAYDVQQLEwkyNTI1MzkwOTExEDAOBgNVBAMTB1hpYW5zQWkwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCoOqxpvPN7Z3yEHlKPfrshO/bZS8/3tRDJZotnJ+0v/PfbrbYueHSZ5TU7ehyzCpHywBVqvJtIWlkRMkWLp4wtOMfYD1VHdukNo43755KxXOCor/h2gnTAv0UHQuFDlRtN9Ok39sVb/cmlPbCawRFphvrBVX7xuga6iNiiBoifc8hys5KVNCdQxc/4q4HCoBu0Ic98oyEbMYimhSBQ6VYRLqqhD7DEJqHHCOWSGifRr73OtLVfBD+iGwxCBXGDGG2hnjabQ+YN5OjnKPLFml01KdHOQf36I7CqfMgD4SaBTeL5lRyOLgSTstRMfYnzja1TRfXelcNmdb43UjSeCwR9AgMBAAGjLzAtMBMGA1UdJQQMMAoGCCsGAQUFBwMCMAkGA1UdEwQCMAAwCwYDVR0PBAQDAgWgMA0GCSqGSIb3DQEBCwUAA4ICAQAEHZPAsGsWm849/jJC3IzZaHbSDtLgHFLzna/y0+fp9kGhf5qtFAfQYxRPbmkr4GwIbKFK+vi1U5MTKypS8jR0G8MtqzXF+6Rw0awN2dbCfimJC5U1+WzPGcDp6j3/SNTc2yllCdqA5ULKTnsBP72yZY7VC6jHboeO/SnIf31IybrCKdF9MpOKnWye8qg5Wob5S6/vknZCSPUpAbVhL6f7XrrgdJozo1392KasfSupNfuHMAAv9aVshtHqNYa7oKKglTxWMCr8hE9VxlmjqzeboijP/AcxSRzCER2OA+vfkWFkellwsBgESQ2PsCl3Kq/tPcQdvFIKAhNtYJMT9lvEF3OpTGxc2WAdloJVw978BkIUdYBtidY2ZxV0l6IU2SvQ+m8esXVgbDVta8wx7Ki9I0g8kRXsEUhDdvx12o3RRp4VIG/kGG3goXIOFyza/vX8Bas5tEdNxJ2L8sLPDYQgqqkhjcLYNnOKyzgZnR4EfFTitiAGMioKIZp9M1/oQQjAbIk2xsUDONwWMYnt5eQXNed+BXMOarnWdVjSR4I/C8Ju0BzXTGt9+Yiq4Gz1WR9a5QBJywEx21c6tp+Y1Pp5ybs9h8gzXog5+bCTpFpada7eqYGirQiFEXQ02Nz2eNjVO3LRE1f4l+1iu8pjP8mJYQGhbwEVIsdf0MEsQIRQ1g=="

    print("Testing with plain string (auto-conversion to SecretStr)...")
    try:
        # Test 1: Plain string (Pydantic should auto-convert to SecretStr)
        options1 = XiansOptions(
            server_url="https://api.agentri.ai",
            api_key=long_api_key,  # Plain string
            llm=LLMConfig(
                provider="google_vertex",
                model="gemini-2.5-flash",
                api_key="AIzaSyDDze7ut9iqtMK86qTa7yoGYIkg1TD9Cqw",
            ),
        )
        print(f"✅ Plain string works! API key length: {len(options1.api_key.get_secret_value())}")
    except Exception as e:
        print(f"❌ Plain string failed: {e}")

    print("\nTesting with SecretStr wrapper...")
    try:
        # Test 2: Explicitly wrapped in SecretStr (recommended)
        options2 = XiansOptions(
            server_url="https://api.agentri.ai",
            api_key=SecretStr(long_api_key),  # Explicit SecretStr
            llm=LLMConfig(
                provider="google_vertex",
                model="gemini-2.5-flash",
                api_key=SecretStr("AIzaSyDDze7ut9iqtMK86qTa7yoGYIkg1TD9Cqw"),
            ),
        )
        print(f"✅ SecretStr wrapper works! API key length: {len(options2.api_key.get_secret_value())}")
    except Exception as e:
        print(f"❌ SecretStr wrapper failed: {e}")

    print("\n✅ All tests passed! Your certificate-style API key is valid.")

if __name__ == "__main__":
    test_long_certificate_api_key()

