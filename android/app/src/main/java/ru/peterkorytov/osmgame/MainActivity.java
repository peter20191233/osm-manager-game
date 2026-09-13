package ru.peterkorytov.osmgame;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.webkit.CookieManager;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;
import android.window.OnBackInvokedDispatcher;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Collections;

/** Offline host. The Python game, runtime and graphics are all inside assets/index.html. */
public final class MainActivity extends Activity {
    public static final String GAME_URL = "https://appassets.androidplatform.net/assets/index.html";
    private static final String HOST = "appassets.androidplatform.net";
    private static final int PAPER = Color.rgb(246, 245, 238);
    private static final int INK = Color.rgb(49, 76, 61);
    private static final String PAUSE_GAME = "(()=>{var p=document.getElementById('pause-button');"
            + "if(p&&!p.disabled&&p.textContent.indexOf('Пауза')!==-1)p.click();})()";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private FrameLayout root;
    private LinearLayout status;
    private WebView webView;
    private AlertDialog exitDialog;
    private boolean wasBackgrounded;
    private int loadGeneration;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        root = new FrameLayout(this);
        root.setBackgroundColor(PAPER);
        setContentView(root);
        configureInsets();
        if (Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::handleBack);
        }
        openGame();
    }

    @SuppressWarnings("deprecation")
    private void configureInsets() {
        if (Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
        }
        int flags = View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
        if (Build.VERSION.SDK_INT >= 26) flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        getWindow().getDecorView().setSystemUiVisibility(flags);
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(Build.VERSION.SDK_INT >= 26 ? Color.TRANSPARENT : INK);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            int left, top, right, bottom;
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets safe = insets.getInsets(WindowInsets.Type.systemBars()
                        | WindowInsets.Type.displayCutout() | WindowInsets.Type.ime());
                left = safe.left; top = safe.top; right = safe.right; bottom = safe.bottom;
            } else {
                left = insets.getSystemWindowInsetLeft();
                top = insets.getSystemWindowInsetTop();
                right = insets.getSystemWindowInsetRight();
                bottom = insets.getSystemWindowInsetBottom();
                if (Build.VERSION.SDK_INT >= 28 && insets.getDisplayCutout() != null) {
                    left = Math.max(left, insets.getDisplayCutout().getSafeInsetLeft());
                    top = Math.max(top, insets.getDisplayCutout().getSafeInsetTop());
                    right = Math.max(right, insets.getDisplayCutout().getSafeInsetRight());
                    bottom = Math.max(bottom, insets.getDisplayCutout().getSafeInsetBottom());
                }
            }
            view.setPadding(left, top, right, bottom);
            return insets;
        });
        root.requestApplyInsets();
    }

    @SuppressLint("SetJavaScriptEnabled")
    @SuppressWarnings("deprecation")
    private void openGame() {
        loadGeneration++;
        final int generation = loadGeneration;
        handler.removeCallbacksAndMessages(null);
        destroyWebView();
        root.removeAllViews();
        try {
            webView = new WebView(this);
            webView.setId(android.R.id.primary);
            webView.setBackgroundColor(PAPER);
            WebView.setWebContentsDebuggingEnabled(false);
            WebSettings settings = webView.getSettings();
            settings.setJavaScriptEnabled(true);
            settings.setDomStorageEnabled(true);
            settings.setAllowFileAccess(false);
            settings.setAllowContentAccess(false);
            settings.setAllowFileAccessFromFileURLs(false);
            settings.setAllowUniversalAccessFromFileURLs(false);
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
            settings.setBlockNetworkLoads(true);
            settings.setGeolocationEnabled(false);
            settings.setJavaScriptCanOpenWindowsAutomatically(false);
            settings.setSupportMultipleWindows(false);
            settings.setMediaPlaybackRequiresUserGesture(true);
            settings.setSupportZoom(false);
            settings.setBuiltInZoomControls(false);
            settings.setDisplayZoomControls(false);
            settings.setTextZoom(100);
            CookieManager.getInstance().setAcceptCookie(false);
            CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);
            webView.setWebChromeClient(new WebChromeClient());
            webView.setWebViewClient(new OfflineClient(generation));
            root.addView(webView, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
            showStatus(false);
            webView.loadUrl(GAME_URL);
            // Covers renderer failures and Python bootstrap errors, including silent failures.
            handler.postDelayed(() -> checkReady(generation, 0), 250);
        } catch (RuntimeException error) {
            // Devices with a missing/disabled system WebView still get a native error screen.
            showStatus(true);
        }
    }

    private void checkReady(int generation, int attempt) {
        if (generation != loadGeneration || webView == null || isFinishing()) return;
        webView.evaluateJavascript("window.osmReady === true", result -> {
            if (generation != loadGeneration || isFinishing()) return;
            if ("true".equals(result)) {
                if (status != null) status.setVisibility(View.GONE);
            } else if (attempt >= 160) {
                showStatus(true);
            } else {
                handler.postDelayed(() -> checkReady(generation, attempt + 1), 250);
            }
        });
    }

    private void showStatus(boolean failed) {
        if (status != null) root.removeView(status);
        status = new LinearLayout(this);
        status.setOrientation(LinearLayout.VERTICAL);
        status.setGravity(Gravity.CENTER);
        status.setPadding(dp(24), dp(24), dp(24), dp(24));
        status.setBackgroundColor(PAPER);
        TextView title = new TextView(this);
        title.setText(failed ? R.string.load_error : R.string.loading);
        title.setTextColor(INK);
        title.setTextSize(22);
        title.setGravity(Gravity.CENTER);
        status.addView(title);
        TextView note = new TextView(this);
        note.setText(failed ? R.string.load_error_note : R.string.loading_note);
        note.setTextColor(INK);
        note.setTextSize(16);
        note.setGravity(Gravity.CENTER);
        note.setPadding(0, dp(14), 0, dp(22));
        status.addView(note);
        if (failed) {
            Button retry = new Button(this);
            retry.setText(R.string.retry);
            retry.setOnClickListener(view -> openGame());
            status.addView(retry);
            Button close = new Button(this);
            close.setText(R.string.exit);
            close.setOnClickListener(view -> finish());
            status.addView(close);
        } else {
            status.addView(new ProgressBar(this));
        }
        root.addView(status, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private static boolean isLocalPage(Uri url) {
        return "https".equals(url.getScheme()) && HOST.equals(url.getEncodedAuthority())
                && "/assets/index.html".equals(url.getPath());
    }

    private void externalLink(Uri url) {
        // Sources are opened outside this privileged local WebView, only after a user tap.
        if (!"https".equals(url.getScheme()) || url.getHost() == null) return;
        pauseGame();
        new AlertDialog.Builder(this)
                .setTitle(R.string.external_title)
                .setMessage(R.string.external_message)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.open_browser, (dialog, which) -> {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, url));
                    } catch (ActivityNotFoundException error) {
                        Toast.makeText(this, R.string.no_browser, Toast.LENGTH_LONG).show();
                    }
                }).show();
    }

    private void pauseGame() {
        if (webView != null) webView.evaluateJavascript(PAUSE_GAME, null);
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        handleBack();
    }

    private void handleBack() {
        if (webView == null) {
            confirmExit();
            return;
        }
        // Back closes the in-game guide/results first, using its existing close handler.
        webView.evaluateJavascript("(()=>{var m=document.getElementById('modal');"
                + "if(m&&m.open){document.getElementById('modal-close').click();return true;}"
                + "return false;})()", closed -> {
            if (!"true".equals(closed) && !isFinishing()) confirmExit();
        });
    }

    private void confirmExit() {
        if (exitDialog != null && exitDialog.isShowing()) return;
        pauseGame();
        exitDialog = new AlertDialog.Builder(this)
                .setTitle(R.string.exit_title)
                .setMessage(R.string.exit_message)
                .setNegativeButton(R.string.stay, null)
                .setPositiveButton(R.string.exit, (dialog, which) -> finish())
                .create();
        exitDialog.show();
    }

    @Override
    protected void onPause() {
        wasBackgrounded = true;
        if (webView != null) {
            WebView pausedView = webView;
            // Suspend timers only AFTER the game has processed its pause button.
            // Suspending first could leave an unexecuted pause callback in the queue.
            pausedView.evaluateJavascript(PAUSE_GAME, result -> {
                if (wasBackgrounded && webView == pausedView) pausedView.pauseTimers();
            });
            pausedView.onPause();
        }
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) {
            webView.resumeTimers();
            webView.onResume();
            if (wasBackgrounded) pauseGame();
        }
        wasBackgrounded = false;
    }

    private void destroyWebView() {
        if (webView == null) return;
        root.removeView(webView);
        webView.stopLoading();
        webView.destroy();
        webView = null;
    }

    @Override
    protected void onDestroy() {
        loadGeneration++;
        handler.removeCallbacksAndMessages(null);
        if (exitDialog != null) exitDialog.dismiss();
        destroyWebView();
        super.onDestroy();
    }

    private final class OfflineClient extends WebViewClient {
        private final int generation;

        OfflineClient(int generation) {
            this.generation = generation;
        }

        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            if (isLocalPage(request.getUrl()) && "GET".equals(request.getMethod())) {
                try {
                    return new WebResourceResponse("text/html", "UTF-8", 200, "OK",
                            Collections.singletonMap("X-Content-Type-Options", "nosniff"),
                            getAssets().open("index.html"));
                } catch (IOException error) {
                    handler.post(() -> { if (generation == loadGeneration) showStatus(true); });
                }
            }
            // Deny by default. No remote fetches, paths, files or runtime downloads are allowed.
            byte[] body = "This resource is not bundled with the game.".getBytes(StandardCharsets.UTF_8);
            return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found",
                    Collections.emptyMap(), new ByteArrayInputStream(body));
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            if (!request.isForMainFrame()) return true;
            if (isLocalPage(request.getUrl())) {
                // Fragment links may scroll within the document, never reload the running game.
                return request.getUrl().getFragment() == null;
            }
            if (request.hasGesture()) externalLink(request.getUrl());
            return true;
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            if (request.isForMainFrame() && generation == loadGeneration) showStatus(true);
        }

        @Override
        public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
            if (request.isForMainFrame() && generation == loadGeneration) showStatus(true);
        }

        @Override
        public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail detail) {
            loadGeneration++;
            handler.removeCallbacksAndMessages(null);
            destroyWebView();
            showStatus(true);
            return true;
        }
    }
}
