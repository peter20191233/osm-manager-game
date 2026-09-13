# Compile-time AndroidX annotations are optional and not used on the device.
-dontwarn com.google.errorprone.annotations.CanIgnoreReturnValue
-dontwarn com.google.errorprone.annotations.MustBeClosed

# AndroidJUnitRunner discovers this test by its public class name and annotations.
-keep class ru.peterkorytov.osmgame.OfflineGameTest { *; }
