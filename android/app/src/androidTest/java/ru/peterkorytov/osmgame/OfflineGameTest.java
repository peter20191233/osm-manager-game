package ru.peterkorytov.osmgame;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.Manifest;
import android.app.Instrumentation;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.os.SystemClock;
import android.provider.MediaStore;
import android.view.MotionEvent;
import android.view.View;
import android.webkit.WebView;

import androidx.lifecycle.Lifecycle;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONTokener;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Exercises the real packaged Python game in Android System WebView.
 * CI disables Wi-Fi and mobile data BEFORE installing and launching the APK.
 * Test-only AndroidX dependencies are not included in the distributed APK.
 */
@RunWith(AndroidJUnit4.class)
public final class OfflineGameTest {
    private final Instrumentation instrumentation =
            InstrumentationRegistry.getInstrumentation();
    private ActivityScenario<MainActivity> scenario;
    private WebView webView;

    @Before
    public void openGame() throws Exception {
        scenario = ActivityScenario.launch(MainActivity.class);
        scenario.onActivity(activity -> webView = activity.findViewById(android.R.id.primary));
        assertNotNull("The game WebView must exist", webView);
        awaitJs("window.osmReady === true", "Python game did not start from bundled assets", 60_000);
        awaitLoadingOverlayHidden();
        assertEquals("Six terminal categories must be available", 6,
                ((Number) evaluate("document.querySelectorAll('.category-button').length")).intValue());
        assertEquals(Boolean.TRUE, evaluate("document.getElementById('load-error').hidden"));
        assertEquals(Boolean.TRUE, evaluate("document.querySelector('.bank-scene').complete && "
                + "document.querySelector('.bank-scene').naturalWidth > 0"));
    }

    @After
    public void closeGame() {
        if (scenario != null) {
            scenario.close();
        }
    }

    @Test
    public void bundledMusicPlaysMutesAndPausesOffline() throws Exception {
        if (!"true".equals(text("document.getElementById('sound-button').getAttribute('aria-pressed')"))) {
            tapOnScreen("sound-button");
        }
        tapOnScreen("next-button");
        String audio = "document.getElementById('background-music')";
        awaitJs(audio + ".readyState >= 2 && !" + audio + ".paused && " + audio + ".currentTime > 0.1",
                "Bundled music must decode and play without network", 15_000);
        assertTrue(((Number) evaluate(audio + ".duration")).doubleValue() > 79);
        assertEquals(Boolean.TRUE, evaluate(audio + ".loop"));
        assertEquals(Boolean.TRUE, evaluate(audio + ".src.startsWith('data:audio/mpeg;base64,')"));
        tapOnScreen("sound-button");
        awaitJs(audio + ".paused", "Mute must stop the music", 5_000);
        assertEquals("0", text("localStorage.getItem('osm-sound')"));
        tapOnScreen("sound-button");
        awaitJs("!" + audio + ".paused", "Unmute must resume music", 5_000);
        tapOnScreen("pause-button");
        awaitJs(audio + ".paused", "Game pause must stop music", 5_000);
        tapOnScreen("pause-button");
        awaitJs("!" + audio + ".paused", "Continue must resume music", 5_000);
        scenario.moveToState(Lifecycle.State.CREATED);
        awaitJs(audio + ".paused", "Backgrounding must stop music", 5_000);
        scenario.moveToState(Lifecycle.State.RESUMED);
        awaitJs(audio + ".paused", "Returning must keep the game paused", 5_000);
    }

    @Test
    public void fullOfflineShiftScoresBothRoutesAndKeepsRecordAfterRelaunch() throws Exception {
        // Use normal player controls. A balanced 12-client deck contains each
        // of the six categories twice; repeatedly choosing accounts therefore
        // exercises two correct and ten incorrect answers without test hooks.
        evaluate("localStorage.removeItem('osm-best-practice')");
        click("mode-practice");
        tapOnScreen("next-button");
        awaitJs("document.body.classList.contains('in-game')", "Start tap was not handled", 10_000);

        int correct = 0;
        int wrong = 0;
        int expectedScore = 0;
        for (int client = 1; client <= 12; client++) {
            awaitJs("!document.getElementById('category-accounts').disabled",
                    "Client " + client + " cannot receive a ticket", 10_000);
            if (client == 1) {
                tapOnScreen("category-accounts");
            } else {
                click("category-accounts");
            }
            awaitJs("document.getElementById('served').textContent === '" + client + "'",
                    "The answer was not counted", 10_000);
            boolean wasCorrect = (Boolean) evaluate(
                    "!document.getElementById('feedback').classList.contains('wrong')");
            if (wasCorrect) {
                correct++;
                expectedScore++;
            } else {
                wrong++;
                expectedScore--;
            }
            assertEquals("Rating must change by exactly +1 or -1", Integer.toString(expectedScore),
                    text("document.getElementById('score').textContent"));
            assertEquals(Boolean.TRUE, evaluate("document.getElementById('category-accounts').disabled"));

            // A second tap while feedback is displayed must not score twice.
            click("category-accounts");
            assertEquals(Integer.toString(client), text("document.getElementById('served').textContent"));
            assertEquals(Integer.toString(expectedScore), text("document.getElementById('score').textContent"));
            if (client == 1) {
                saveScreenshot("smoke-game.png");
            }
            click("next-button");
        }
        assertEquals("Balanced deck must include two accounts requests", 2, correct);
        assertEquals(10, wrong);
        assertEquals(-8, expectedScore);
        awaitJs("document.getElementById('modal').open && !!document.querySelector('.result-score')",
                "Shift results did not appear", 10_000);
        assertEquals("-8", text("localStorage.getItem('osm-best-practice')"));
        saveScreenshot("smoke-result.png");

        scenario.close();
        scenario = ActivityScenario.launch(MainActivity.class);
        scenario.onActivity(activity -> webView = activity.findViewById(android.R.id.primary));
        awaitJs("window.osmReady === true", "Offline relaunch failed", 60_000);
        click("mode-practice");
        assertEquals("-8", text("localStorage.getItem('osm-best-practice')"));
        assertTrue("Saved record must be shown to the player",
                text("document.getElementById('best-label').textContent").contains("-8"));
    }

    @Test
    public void backgroundingPausesCurrentClientAndResumeKeepsProgress() throws Exception {
        click("next-button");
        awaitJs("!document.getElementById('category-accounts').disabled", "Shift did not start", 10_000);
        String request = text("document.getElementById('client-request').textContent");

        // ActivityScenario invokes the real Android pause/stop/resume callbacks.
        scenario.moveToState(Lifecycle.State.CREATED);
        SystemClock.sleep(1_500);
        scenario.moveToState(Lifecycle.State.RESUMED);
        awaitJs("document.getElementById('pause-button').textContent.indexOf('Продолжить') >= 0",
                "Returning from background must leave the shift paused", 10_000);
        assertEquals(request, text("document.getElementById('client-request').textContent"));
        assertEquals("0", text("document.getElementById('score').textContent"));
        assertEquals("0", text("document.getElementById('served').textContent"));
        assertEquals(Boolean.TRUE, evaluate("document.getElementById('category-accounts').disabled"));
        String pausedTime = text("document.getElementById('patience-fill').style.width");
        SystemClock.sleep(1_250);
        assertEquals("Timer must remain stopped until the player resumes", pausedTime,
                text("document.getElementById('patience-fill').style.width"));

        click("pause-button");
        awaitJs("!document.getElementById('category-accounts').disabled", "Continue did not resume play", 10_000);
        click("category-accounts");
        awaitJs("document.getElementById('served').textContent === '1'", "Resumed game cannot score", 10_000);
    }

    @Test
    public void installedApkIsSelfContainedAndNeedsNoNetworkPermission() throws Exception {
        Context context = instrumentation.getTargetContext();
        Bundle arguments = InstrumentationRegistry.getArguments();
        if ("true".equals(arguments.getString("expectedRelease"))) {
            assertFalse("The distributed release must not be debuggable",
                    (context.getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0);
            String expectedCertificate = normalizeSha256(arguments.getString("expectedCertificate"),
                    "expectedCertificate is required when expectedRelease=true");
            PackageInfo installed = context.getPackageManager().getPackageInfo(
                    context.getPackageName(), PackageManager.GET_SIGNING_CERTIFICATES);
            assertNotNull("Installed APK signing information is missing", installed.signingInfo);
            assertFalse("The release must have one current signing identity",
                    installed.signingInfo.hasMultipleSigners());
            Signature[] history = installed.signingInfo.getSigningCertificateHistory();
            assertNotNull("Installed APK signing certificate is missing", history);
            assertTrue("Installed APK signing certificate is missing", history.length > 0);
            // The last entry is the current certificate; preceding entries are any rotation history.
            byte[] currentCertificate = history[history.length - 1].toByteArray();
            assertEquals("Installed release certificate does not match the public release fingerprint",
                    expectedCertificate, hex(MessageDigest.getInstance("SHA-256").digest(currentCertificate)));
        }
        String expectedApkSha256 = arguments.getString("expectedApkSha256");
        if (expectedApkSha256 != null) {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream input = new FileInputStream(context.getApplicationInfo().sourceDir)) {
                byte[] buffer = new byte[32_768];
                int count;
                while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
            }
            assertEquals("The installed APK must be exactly the signed file selected for release",
                    normalizeSha256(expectedApkSha256, "expectedApkSha256 must be a SHA-256 digest"),
                    hex(digest.digest()));
        }
        assertEquals("Offline game must not request Internet access", PackageManager.PERMISSION_DENIED,
                context.getPackageManager().checkPermission(Manifest.permission.INTERNET, context.getPackageName()));
        try (ZipFile apk = new ZipFile(context.getApplicationInfo().sourceDir)) {
            ZipEntry bundledGame = apk.getEntry("assets/index.html");
            assertNotNull("The playable game must be included in the installed APK", bundledGame);
            assertTrue("Bundled HTML must include the Python browser runtime", bundledGame.getSize() > 1_000_000);
            Enumeration<? extends ZipEntry> entries = apk.entries();
            while (entries.hasMoreElements()) {
                String name = entries.nextElement().getName();
                assertFalse("Universal lightweight APK must not include native ABI libraries: " + name,
                        name.startsWith("lib/") || name.endsWith(".so"));
            }
        }
        assertEquals("appassets.androidplatform.net", text("location.hostname"));
    }

    private void click(String id) throws Exception {
        evaluate("document.getElementById(" + JSONObject.quote(id) + ").click()");
    }

    private void awaitLoadingOverlayHidden() {
        long deadline = SystemClock.elapsedRealtime() + 10_000;
        AtomicReference<Boolean> loadingVisible = new AtomicReference<>(true);
        while (SystemClock.elapsedRealtime() < deadline) {
            scenario.onActivity(activity -> {
                ArrayList<View> matches = new ArrayList<>();
                // Release R8 inlines the app's non-final R fields and removes
                // the generated R class. Resolve the still-used resource by name.
                int loadingId = activity.getResources().getIdentifier(
                        "loading", "string", activity.getPackageName());
                assertTrue("The native loading label resource must exist", loadingId != 0);
                activity.getWindow().getDecorView().findViewsWithText(matches,
                        activity.getString(loadingId), View.FIND_VIEWS_WITH_TEXT);
                loadingVisible.set(false);
                for (View match : matches) {
                    if (match.isShown()) loadingVisible.set(true);
                }
            });
            if (!loadingVisible.get()) return;
            SystemClock.sleep(100);
        }
        throw new AssertionError("Native loading screen is still covering the ready game");
    }

    /** Actual Android touches verify the WebView input path, not just DOM handlers. */
    private void tapOnScreen(String id) throws Exception {
        evaluate("document.getElementById(" + JSONObject.quote(id)
                + ").scrollIntoView({block:'center', behavior:'instant'})");
        SystemClock.sleep(250);
        JSONArray position = (JSONArray) evaluate("(function(){var r=document.getElementById("
                + JSONObject.quote(id) + ").getBoundingClientRect();return [r.left+r.width/2,"
                + "r.top+r.height/2,window.innerWidth,window.innerHeight];})()");
        assertTrue("Tapped button must be visible: " + id, position.getDouble(1) >= 0
                && position.getDouble(1) <= position.getDouble(3));
        int[] origin = new int[2];
        int[] dimensions = new int[1];
        instrumentation.runOnMainSync(() -> {
            webView.getLocationOnScreen(origin);
            dimensions[0] = webView.getWidth();
        });
        float scale = dimensions[0] / (float) position.getDouble(2);
        float x = origin[0] + (float) position.getDouble(0) * scale;
        float y = origin[1] + (float) position.getDouble(1) * scale;
        long down = SystemClock.uptimeMillis();
        MotionEvent press = MotionEvent.obtain(down, down, MotionEvent.ACTION_DOWN, x, y, 0);
        MotionEvent release = MotionEvent.obtain(down, down + 50, MotionEvent.ACTION_UP, x, y, 0);
        try {
            instrumentation.sendPointerSync(press);
            instrumentation.sendPointerSync(release);
        } finally {
            press.recycle();
            release.recycle();
        }
        instrumentation.waitForIdleSync();
    }

    private String text(String expression) throws Exception {
        Object value = evaluate(expression);
        return value == JSONObject.NULL ? null : String.valueOf(value);
    }

    private Object evaluate(String expression) throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> result = new AtomicReference<>();
        instrumentation.runOnMainSync(() -> webView.evaluateJavascript(expression, value -> {
            result.set(value);
            done.countDown();
        }));
        assertTrue("WebView did not answer JavaScript: " + expression, done.await(10, TimeUnit.SECONDS));
        return new JSONTokener(result.get()).nextValue();
    }

    private void awaitJs(String expression, String failure, long timeoutMs) throws Exception {
        long deadline = SystemClock.elapsedRealtime() + timeoutMs;
        Object last = null;
        while (SystemClock.elapsedRealtime() < deadline) {
            last = evaluate(expression);
            if (Boolean.TRUE.equals(last)) {
                return;
            }
            SystemClock.sleep(100);
        }
        throw new AssertionError(failure + " (last result: " + last + ")");
    }

    private void saveScreenshot(String name) throws Exception {
        Bitmap image = instrumentation.getUiAutomation().takeScreenshot();
        assertNotNull("Android screenshot capture failed", image);
        ContentResolver resolver = instrumentation.getTargetContext().getContentResolver();
        ContentValues values = new ContentValues();
        values.put(MediaStore.Images.Media.DISPLAY_NAME, name);
        values.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
        values.put(MediaStore.Images.Media.RELATIVE_PATH,
                Environment.DIRECTORY_PICTURES + "/OSMReleaseQA");
        values.put(MediaStore.Images.Media.IS_PENDING, 1);
        Uri imageUri = null;
        boolean published = false;
        try {
            // Shared media survives the test runner uninstalling the APK. These
            // writes occur only on the disposable emulator, without storage permissions.
            imageUri = resolver.insert(MediaStore.Images.Media.getContentUri(
                    MediaStore.VOLUME_EXTERNAL_PRIMARY), values);
            assertNotNull("Could not create the screenshot media entry", imageUri);
            try (OutputStream output = resolver.openOutputStream(imageUri, "w")) {
                assertNotNull("Could not open the screenshot media entry", output);
                assertTrue(image.compress(Bitmap.CompressFormat.PNG, 100, output));
            }
            values.clear();
            values.put(MediaStore.Images.Media.IS_PENDING, 0);
            assertEquals("Could not publish the completed screenshot", 1,
                    resolver.update(imageUri, values, null, null));
            published = true;
        } finally {
            image.recycle();
            if (!published && imageUri != null) resolver.delete(imageUri, null, null);
        }
    }

    private static String normalizeSha256(String value, String message) {
        assertNotNull(message, value);
        String normalized = value.trim().replace(":", "").toLowerCase(Locale.ROOT);
        assertTrue(message, normalized.matches("[0-9a-f]{64}"));
        return normalized;
    }

    private static String hex(byte[] bytes) {
        char[] digits = "0123456789abcdef".toCharArray();
        char[] result = new char[bytes.length * 2];
        for (int index = 0; index < bytes.length; index++) {
            result[index * 2] = digits[(bytes[index] & 0xff) >>> 4];
            result[index * 2 + 1] = digits[bytes[index] & 0x0f];
        }
        return new String(result);
    }
}
