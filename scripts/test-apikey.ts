/**
 * Test script to debug API key saving for Lichess
 * 
 * Run with: npx ts-node scripts/test-apikey.ts
 */

import prisma from '../lib/prisma'
import { encrypt, decrypt } from '../lib/encryption'

const TEST_USER_EMAIL = 'test@example.com'
const TEST_LICHESS_USERNAME = 'DrNykterstein' // Magnus Carlsen's Lichess username

async function testApiKeyFlow() {
    console.log('=== API Key Test Script ===\n')

    // Step 1: Test encryption
    console.log('1. Testing encryption...')
    try {
        const testString = 'test-api-key-123'
        const encrypted = encrypt(testString)
        const decrypted = decrypt(encrypted)

        if (decrypted === testString) {
            console.log('   ✅ Encryption/decryption working correctly')
        } else {
            console.log('   ❌ Encryption/decryption mismatch!')
            console.log(`   Original: ${testString}`)
            console.log(`   Decrypted: ${decrypted}`)
        }
    } catch (err) {
        console.log('   ❌ Encryption failed!')
        console.log(`   Error: ${err instanceof Error ? err.message : String(err)}`)
        console.log('\n   💡 Make sure ENCRYPTION_KEY is set to a valid 64-character hex string in .env')
        return
    }

    // Step 2: Test database connection
    console.log('\n2. Testing database connection...')
    try {
        await prisma.$connect()
        console.log('   ✅ Database connected')
    } catch (err) {
        console.log('   ❌ Database connection failed!')
        console.log(`   Error: ${err instanceof Error ? err.message : String(err)}`)
        return
    }

    // Step 3: Create or get test user
    console.log('\n3. Getting/creating test user...')
    let user
    try {
        user = await prisma.user.upsert({
            where: { email: TEST_USER_EMAIL },
            update: {},
            create: {
                email: TEST_USER_EMAIL,
                name: 'Test User',
                hashedPassword: 'test-hash'
            }
        })
        console.log(`   ✅ User ready: ${user.id}`)
    } catch (err) {
        console.log('   ❌ Failed to create/get user!')
        console.log(`   Error: ${err instanceof Error ? err.message : String(err)}`)
        return
    }

    // Step 4: Validate Lichess username
    console.log('\n4. Validating Lichess username...')
    try {
        const res = await fetch(`https://lichess.org/api/user/${encodeURIComponent(TEST_LICHESS_USERNAME)}`)
        if (res.ok) {
            const data = await res.json()
            console.log(`   ✅ Username valid: ${data.username}`)
        } else {
            console.log(`   ❌ Username not found on Lichess (status: ${res.status})`)
            return
        }
    } catch (err) {
        console.log('   ❌ Failed to validate username!')
        console.log(`   Error: ${err instanceof Error ? err.message : String(err)}`)
        return
    }

    // Step 5: Delete any existing API key for this user/platform combo
    console.log('\n5. Cleaning up existing API key...')
    try {
        await prisma.apiKey.deleteMany({
            where: {
                userId: user.id,
                platform: 'LICHESS'
            }
        })
        console.log('   ✅ Cleanup done')
    } catch (err) {
        console.log('   ❌ Cleanup failed!')
        console.log(`   Error: ${err instanceof Error ? err.message : String(err)}`)
    }

    // Step 6: Create API key
    console.log('\n6. Creating API key in database...')
    try {
        const encryptedKey = encrypt('lip_test_token_placeholder')

        const saved = await prisma.apiKey.create({
            data: {
                userId: user.id,
                platform: 'LICHESS',
                username: TEST_LICHESS_USERNAME,
                apiKey: encryptedKey,
                isValid: true
            }
        })
        console.log(`   ✅ API key created: ${saved.id}`)
        console.log(`   Platform: ${saved.platform}`)
        console.log(`   Username: ${saved.username}`)
        console.log(`   Is Valid: ${saved.isValid}`)
    } catch (err) {
        console.log('   ❌ Failed to create API key!')
        console.log(`   Error: ${err instanceof Error ? err.message : String(err)}`)

        // Check for unique constraint violation
        if (err instanceof Error && err.message.includes('Unique constraint')) {
            console.log('\n   💡 This might be a duplicate key issue.')
        }
        return
    }

    // Step 7: Read back and verify
    console.log('\n7. Reading back API key...')
    try {
        const apiKeys = await prisma.apiKey.findMany({
            where: { userId: user.id }
        })
        console.log(`   ✅ Found ${apiKeys.length} API key(s)`)

        for (const key of apiKeys) {
            console.log(`   - ${key.platform}: ${key.username} (valid: ${key.isValid})`)

            // Try to decrypt
            try {
                const decrypted = decrypt(key.apiKey)
                console.log(`     Decryption: ✅ Success`)
            } catch (decryptErr) {
                console.log(`     Decryption: ❌ Failed`)
            }
        }
    } catch (err) {
        console.log('   ❌ Failed to read API keys!')
        console.log(`   Error: ${err instanceof Error ? err.message : String(err)}`)
    }

    // Cleanup
    console.log('\n8. Cleaning up test data...')
    try {
        await prisma.apiKey.deleteMany({ where: { userId: user.id } })
        await prisma.user.delete({ where: { id: user.id } })
        console.log('   ✅ Test data cleaned up')
    } catch (err) {
        console.log('   ⚠️  Cleanup warning (non-critical)')
    }

    console.log('\n=== Test Complete ===')
    await prisma.$disconnect()
}

// Run the test
testApiKeyFlow().catch(err => {
    console.error('Unexpected error:', err)
    process.exit(1)
})
