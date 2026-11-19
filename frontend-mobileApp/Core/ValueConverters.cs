using System.Globalization;
namespace SalesMobileApp.Core;
public sealed class StringNotEmptyConverter : IValueConverter { public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture) => !string.IsNullOrWhiteSpace(value?.ToString()); public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) => throw new NotSupportedException(); }
public sealed class InverseBoolConverter : IValueConverter { public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture) => value is bool b && !b; public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) => throw new NotSupportedException(); }
